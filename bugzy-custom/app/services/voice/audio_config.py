"""
Audio configuration for Bugzy Voice Agent.

This module centralises STT and TTS configuration so it can be
shared between the LiveKit agent and any test utilities.
"""

# ─── Deepgram STT ─────────────────────────────────────────────────────────────

DEEPGRAM_STT_CONFIG: dict = {
    "model": "nova-2",
    "language": "en-IN",
    "smart_format": True,
    "punctuate": True,
    "interim_results": True,
    "endpointing": 200,  # ms – shorter for faster voice turn detection
}

# ─── Google Cloud TTS ─────────────────────────────────────────────────────────

GOOGLE_TTS_CONFIG: dict = {
    "language": "en-IN",
    "voice_name": "en-IN-Chirp3-HD-Aoede",
}

# ─── Silero VAD ───────────────────────────────────────────────────────────────

SILERO_VAD_CONFIG: dict = {
    "min_speech_duration": 0.1,   # seconds – faster speech detection
    "min_silence_duration": 0.2,  # seconds – faster turn detection for voice
}

# ─── Voice Assistant ──────────────────────────────────────────────────────────

VOICE_ASSISTANT_CONFIG: dict = {
    "allow_interruptions": True,
    "interrupt_min_words": 2,  # words before an interruption is accepted
}

# ─── Python Audio Bridge ──────────────────────────────────────────────────────

PYTHON_BRIDGE_WS_PORT: int = 8001          # WebSocket server for raw PCM audio
PYTHON_BRIDGE_HTTP_PORT: int = 9001        # HTTP server for call registration
NODE_BACKEND_PORT: int = 3000              # Node.js WhatsApp backend port
