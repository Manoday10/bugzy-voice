"""
WhatsApp ↔ LiveKit Audio Bridge (Python side).

Direct port of bugzy-voice/app/python-bridge/audio_bridge.py adapted for
the bugzy-custom import paths and MongoDB-based session management.

Architecture:
  Node.js AudioBridge  ──WebSocket (raw PCM)──►  WhatsAppLiveKitBridge
                                                        │
                                                LiveKit Room (as participant)
                                                        │
                                                LiveKit Agent (GPT/TTS)

One BridgeManager instance handles ALL concurrent calls in a single process.
Node.js registers each incoming call via a small HTTP endpoint (/register),
then opens a WebSocket connection at /<call_id> to stream PCM audio.
"""

import asyncio
import logging
import os
from urllib.parse import urlparse
from typing import Optional

import websockets
from dotenv import load_dotenv
from livekit import api, rtc

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ─── LiveKit credentials ──────────────────────────────────────────────────────

LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")

# Ports (configurable via env so bridge and agent can run together)
from app.services.voice.audio_config import PYTHON_BRIDGE_WS_PORT, PYTHON_BRIDGE_HTTP_PORT  # noqa: E402


# ─── Bridge for a single call ─────────────────────────────────────────────────


class WhatsAppLiveKitBridge:
    """
    Bridges audio for ONE WhatsApp call to a LiveKit room.

    Lifecycle:
        1. Node.js calls /register (HTTP) → BridgeManager.register_bridge()
        2. Node.js opens WebSocket at /<call_id> → handle_nodejs_audio() runs
        3. Bridge joins LiveKit room as the caller participant (phone_number as identity)
        4. PCM chunks from Node.js → LiveKit (user speech → agent STT)
        5. Agent audio from LiveKit → Node.js → WhatsApp (TTS output)
    """

    def __init__(
        self, call_id: str, room_name: str, phone_number: Optional[str] = None
    ) -> None:
        self.call_id = call_id
        self.room_name = room_name
        # Use phone number as LiveKit identity so the agent can do CRM lookup
        self.phone_number = phone_number or f"whatsapp-bridge-{call_id}"
        self.room: Optional[rtc.Room] = None
        self.audio_source: Optional[rtc.AudioSource] = None
        self.nodejs_ws: Optional[websockets.WebSocketServerProtocol] = None
        self.running = False
        self._sent_frames = 0

    # ─── Token ────────────────────────────────────────────────────────────────

    def _generate_token(self) -> str:
        """Generate a LiveKit access token for this caller."""
        token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.with_identity(self.phone_number)
        token.with_name("WhatsApp Caller")
        token.with_grants(
            api.VideoGrants(
                room_join=True,
                room=self.room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        return token.to_jwt()

    # ─── LiveKit ──────────────────────────────────────────────────────────────

    async def connect_to_livekit(self) -> None:
        """Connect to the LiveKit room and publish a microphone audio track."""
        logger.info("[%s] Connecting to LiveKit room: %s", self.call_id, self.room_name)

        self.room = rtc.Room()
        token = self._generate_token()

        @self.room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.TrackPublication,
            participant: rtc.RemoteParticipant,
        ) -> None:
            logger.info("[%s] Subscribed to %s track from %s", self.call_id, track.kind, participant.identity)
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                asyncio.create_task(self._forward_agent_audio(track))

        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
            logger.info("[%s] Participant connected: %s", self.call_id, participant.identity)

        await self.room.connect(LIVEKIT_URL, token)
        logger.info("[%s] Connected to LiveKit as %s", self.call_id, self.room.local_participant.identity)

        # Publish the WhatsApp audio track (48 kHz mono – standard wrtc output)
        self.audio_source = rtc.AudioSource(48000, 1)
        track = rtc.LocalAudioTrack.create_audio_track("whatsapp-audio", self.audio_source)
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        await self.room.local_participant.publish_track(track, options)
        logger.info("[%s] Published WhatsApp audio track to LiveKit", self.call_id)

    # ─── Agent audio forwarding ───────────────────────────────────────────────

    async def _forward_agent_audio(self, track: rtc.Track) -> None:
        """Stream LiveKit agent audio back to Node.js as raw PCM bytes."""
        logger.info("[%s] Starting agent-audio forwarding to Node.js", self.call_id)
        audio_stream = rtc.AudioStream(track)
        async for event in audio_stream:
            if self.nodejs_ws:
                audio_bytes = event.frame.data.tobytes()
                if self._sent_frames == 0:
                    logger.info(
                        "[%s] First agent audio frame: %d bytes, sr=%d, ch=%d",
                        self.call_id,
                        len(audio_bytes),
                        event.frame.sample_rate,
                        event.frame.num_channels,
                    )
                try:
                    await self.nodejs_ws.send(audio_bytes)
                    self._sent_frames += 1
                    if self._sent_frames % 100 == 0:
                        logger.debug("[%s] Forwarded %d agent audio frames", self.call_id, self._sent_frames)
                except Exception as exc:
                    logger.error("[%s] Error forwarding agent audio: %s", self.call_id, exc)

    # ─── Node.js audio handling ───────────────────────────────────────────────

    async def handle_nodejs_audio(
        self, websocket: websockets.WebSocketServerProtocol
    ) -> None:
        """
        Receive raw PCM audio from Node.js and push it to LiveKit.

        Node.js sends Int16 PCM at 48 kHz mono (10 ms chunks = 960 bytes).
        """
        logger.info("[%s] Starting PCM reception from Node.js", self.call_id)
        try:
            async for message in websocket:
                if not self.audio_source or not message:
                    continue

                # Validate frame alignment
                sample_rate = 48000
                num_channels = 1
                bytes_per_sample = 2
                expected_align = num_channels * bytes_per_sample

                if len(message) % expected_align != 0:
                    logger.warning("[%s] Invalid frame length: %d bytes", self.call_id, len(message))
                    continue

                samples_per_channel = len(message) // expected_align
                frame = rtc.AudioFrame(
                    data=message,
                    sample_rate=sample_rate,
                    num_channels=num_channels,
                    samples_per_channel=samples_per_channel,
                )
                await self.audio_source.capture_frame(frame)

        except websockets.exceptions.ConnectionClosed:
            logger.info("[%s] Node.js WebSocket closed", self.call_id)
        except Exception as exc:
            logger.error("[%s] Error in handle_nodejs_audio: %s", self.call_id, exc)
        finally:
            self.nodejs_ws = None
            self.running = False

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """Start bridging: connect to LiveKit, then handle Node.js audio stream."""
        self.running = True
        self.nodejs_ws = websocket
        try:
            await self.connect_to_livekit()
            logger.info("[%s] Bridge started — listening for PCM audio", self.call_id)
            # Launch audio handling in the background, keep bridge alive
            asyncio.create_task(self.handle_nodejs_audio(websocket))
        except Exception as exc:
            logger.error("[%s] Bridge start failed: %s", self.call_id, exc, exc_info=True)
            await self.cleanup()
            raise

    async def cleanup(self) -> None:
        """Disconnect from LiveKit and close the WebSocket."""
        logger.info("[%s] Cleaning up bridge", self.call_id)
        self.running = False
        if self.room:
            try:
                await self.room.disconnect()
            except Exception:
                pass
        if self.nodejs_ws:
            try:
                await self.nodejs_ws.close()
            except Exception:
                pass


# ─── Multi-call manager ────────────────────────────────────────────────────────


class BridgeManager:
    """
    Manages all active WhatsAppLiveKitBridge instances in a single process.

    Exposes:
    - WebSocket server on PYTHON_BRIDGE_WS_PORT for raw audio streams
    - HTTP server on PYTHON_BRIDGE_HTTP_PORT for call registration (/register)
    """

    def __init__(self) -> None:
        self._bridges: dict[str, WhatsAppLiveKitBridge] = {}
        self._lock = asyncio.Lock()

    # ─── WebSocket handler ────────────────────────────────────────────────────

    async def handle_websocket_connection(
        self, websocket: websockets.WebSocketServerProtocol
    ) -> None:
        """
        Handle a new WebSocket connection from Node.js.

        URL path format: ws://localhost:<WS_PORT>/<call_id>
        """
        path = (
            websocket.request.path
            if hasattr(websocket, "request")
            else getattr(websocket, "path", "")
        )
        call_id = path.lstrip("/") if path else None

        if not call_id:
            logger.error("No call_id in WebSocket path — refusing connection")
            await websocket.close(1008, "Missing call_id in path")
            return

        logger.info("New WebSocket connection for call: %s", call_id)

        async with self._lock:
            bridge = self._bridges.get(call_id)

        if not bridge:
            logger.error("No bridge registered for call %s — refusing connection", call_id)
            await websocket.close(1008, f"No bridge for call {call_id}")
            return

        try:
            await bridge.start(websocket)
            # Keep the connection alive while the bridge is running
            while bridge.running:
                await asyncio.sleep(1)
        except Exception as exc:
            logger.error("Error in WebSocket handler for call %s: %s", call_id, exc)
        finally:
            await self.remove_bridge(call_id)

    # ─── Registration ─────────────────────────────────────────────────────────

    async def register_bridge(
        self, call_id: str, room_name: str, phone_number: Optional[str] = None
    ) -> bool:
        """Register a new bridge for an incoming call (idempotent)."""
        async with self._lock:
            if call_id in self._bridges:
                logger.warning("Bridge for call %s already exists", call_id)
                return False
            bridge = WhatsAppLiveKitBridge(call_id, room_name, phone_number)
            self._bridges[call_id] = bridge
            logger.info(
                "Registered bridge for call %s (total active: %d)",
                call_id,
                len(self._bridges),
            )
            return True

    async def remove_bridge(self, call_id: str) -> None:
        """Remove and clean up a bridge after the call ends."""
        async with self._lock:
            bridge = self._bridges.pop(call_id, None)
        if bridge:
            await bridge.cleanup()
            logger.info("Removed bridge for call %s (remaining: %d)", call_id, len(self._bridges))

    # ─── Server startup ───────────────────────────────────────────────────────

    async def start_ws_server(self, port: int = PYTHON_BRIDGE_WS_PORT) -> None:
        """Start WebSocket server that accepts PCM audio from Node.js."""
        logger.info("Starting WebSocket bridge server on port %d", port)
        server = await websockets.serve(
            self.handle_websocket_connection,
            "0.0.0.0",
            port,
        )
        logger.info("WebSocket bridge ready at ws://localhost:%d", port)
        await asyncio.Future()  # run forever


# ─── HTTP registration server ─────────────────────────────────────────────────


async def start_http_server(manager: BridgeManager, port: int = PYTHON_BRIDGE_HTTP_PORT) -> None:
    """
    Start a lightweight aiohttp server for call registration.

    Node.js calls POST /register with {call_id, room_name, phone_number}
    before opening the WebSocket connection.
    """
    from aiohttp import web

    async def register_call(request: web.Request) -> web.Response:
        try:
            data = await request.json()
            call_id = data.get("call_id")
            room_name = data.get("room_name")
            phone_number = data.get("phone_number")

            if not call_id or not room_name:
                return web.json_response({"error": "Missing call_id or room_name"}, status=400)

            success = await manager.register_bridge(call_id, room_name, phone_number)
            if success:
                return web.json_response({"status": "registered", "call_id": call_id})
            return web.json_response({"error": "Bridge already exists"}, status=409)

        except Exception as exc:
            logger.error("Error in /register: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def health(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok",
                "active_bridges": len(manager._bridges),
                "bridge_ids": list(manager._bridges.keys()),
            }
        )

    app = web.Application()
    app.router.add_post("/register", register_call)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("HTTP registration server running at http://localhost:%d", port)


# ─── Entry point ──────────────────────────────────────────────────────────────


async def main(ws_port: int = PYTHON_BRIDGE_WS_PORT, http_port: int = PYTHON_BRIDGE_HTTP_PORT) -> None:
    """Run the multi-call bridge: WebSocket + HTTP servers together."""
    logger.info("=" * 60)
    logger.info("Bugzy WhatsApp-LiveKit Audio Bridge")
    logger.info("=" * 60)
    logger.info("WS port : %d", ws_port)
    logger.info("HTTP port: %d", http_port)
    logger.info("LiveKit  : %s", LIVEKIT_URL)
    logger.info("=" * 60)

    if not LIVEKIT_URL or not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        logger.error("CRITICAL: LiveKit credentials not set — check your .env file")
        return

    manager = BridgeManager()

    # Run HTTP server in background, WebSocket server in foreground
    asyncio.create_task(start_http_server(manager, http_port))

    try:
        await manager.start_ws_server(ws_port)
    except KeyboardInterrupt:
        logger.info("Shutting down bridge server…")


if __name__ == "__main__":
    import sys

    _ws_port = int(sys.argv[1]) if len(sys.argv) > 1 else PYTHON_BRIDGE_WS_PORT
    _http_port = int(sys.argv[2]) if len(sys.argv) > 2 else PYTHON_BRIDGE_HTTP_PORT
    asyncio.run(main(_ws_port, _http_port))
