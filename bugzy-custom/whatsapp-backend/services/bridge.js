/**
 * bridge.js — WhatsApp WebRTC ↔ LiveKit Bridge
 *
 * Orchestrates the full call setup for each incoming WhatsApp call:
 *   1. Creates a Node.js-side WebRTC PeerConnection (using @roamhq/wrtc)
 *   2. Sets up the SDP offer/answer exchange with WhatsApp
 *   3. Creates a LiveKit room for the call
 *   4. Registers the call with the Python audio bridge (POST /register)
 *   5. Starts the AudioBridge (RTCAudioSink → Python WS, Python → RTCAudioSource)
 *
 * Adapted from bugzy-voice/app/whatsapp-backend/services/bridge.js
 */

'use strict';

// Polyfill required before wrtc import
const { ReadableStream, WritableStream, TransformStream } = require('web-streams-polyfill');
global.ReadableStream = global.ReadableStream || ReadableStream;
global.WritableStream = global.WritableStream || WritableStream;
global.TransformStream = global.TransformStream || TransformStream;

const util = require('util');
const axios = require('axios');

const { RTCPeerConnection } = require('@roamhq/wrtc');

const livekitService = require('./livekit');
const whatsappService = require('./whatsapp');
const AudioBridge = require('./audio-bridge');
const logger = require('../utils/logger');

// Config
const PYTHON_HTTP_PORT = parseInt(process.env.PYTHON_HTTP_PORT || '9001', 10);


// ─── Single call bridge ────────────────────────────────────────────────────────

class WhatsAppLiveKitBridge {
    /**
     * @param {string} callId       WhatsApp call ID
     * @param {string} fromPhone    Caller phone number
     * @param {string} sdpOffer     SDP offer from WhatsApp
     * @param {string} roomName     LiveKit room name
     */
    constructor(callId, fromPhone, sdpOffer, roomName) {
        this.callId = callId;
        this.fromPhone = fromPhone;
        this.sdpOffer = sdpOffer;
        this.roomName = roomName;
        this.pc = null;
        this.audioBridge = null;
        this.returnAudioSource = null;  // Pre-created for SDP (like bugzy-voice)
    }

    // ─── WebRTC SDP exchange ─────────────────────────────────────────────────

    async _createPeerConnection() {
        const config = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
            ],
        };
        this.pc = new RTCPeerConnection(config);

        this.pc.onicecandidate = (event) => {
            if (event.candidate) {
                logger.debug(`[${this.callId}] New ICE candidate`, { candidate: event.candidate.candidate?.slice(0, 80) });
            }
        };

        this.pc.onconnectionstatechange = () => {
            logger.info(`[${this.callId}] ICE connection state: ${this.pc.connectionState}`);
            if (this.pc.connectionState === 'disconnected' || this.pc.connectionState === 'failed') {
                logger.warn(`[${this.callId}] PeerConnection disconnected/failed — cleaning up`);
                this._cleanup();
            }
        };

        // CRITICAL (bugzy-voice pattern): Create return audio track BEFORE SDP exchange
        // so createAnswer() includes our send capability — WhatsApp can then receive agent audio
        const { nonstandard } = require('@roamhq/wrtc');
        const { RTCAudioSource } = nonstandard;
        this.returnAudioSource = new RTCAudioSource();
        const returnAudioTrack = this.returnAudioSource.createTrack();
        this.pc.addTrack(returnAudioTrack);
        logger.info(`[${this.callId}] Return audio track added to PeerConnection (before SDP)`);

        // Capture incoming audio track — AudioBridge starts when WhatsApp track arrives
        this.pc.ontrack = async (event) => {
            logger.info(`[${this.callId}] Received track from caller`, { kind: event.track.kind });
            if (event.track.kind === 'audio') {
                this.audioBridge = new AudioBridge(this.callId, this.pc, event.track, this.returnAudioSource);
                try {
                    await this.audioBridge.start();
                    logger.info(`[${this.callId}] AudioBridge started successfully`);
                } catch (err) {
                    logger.error(`[${this.callId}] AudioBridge failed to start`, err);
                }
            }
        };

        return this.pc;
    }

    async _generateSdpAnswer(sdpOffer) {
        await this.pc.setRemoteDescription({ type: 'offer', sdp: sdpOffer });

        const answer = await this.pc.createAnswer();
        await this.pc.setLocalDescription(answer);

        // Wait for ICE gathering to complete (or timeout after 5 s)
        await new Promise((resolve) => {
            if (this.pc.iceGatheringState === 'complete') return resolve();
            const timeout = setTimeout(resolve, 5000);
            this.pc.onicegatheringstatechange = () => {
                if (this.pc.iceGatheringState === 'complete') {
                    clearTimeout(timeout);
                    resolve();
                }
            };
        });

        logger.info(`[${this.callId}] ICE gathering complete`);
        return this.pc.localDescription.sdp;
    }

    // ─── Python bridge registration ──────────────────────────────────────────

    async _registerWithPythonBridge() {
        const url = `http://localhost:${PYTHON_HTTP_PORT}/register`;
        logger.info(`[${this.callId}] Registering with Python bridge`, { url, roomName: this.roomName });

        await axios.post(
            url,
            {
                call_id: this.callId,
                room_name: this.roomName,
                phone_number: this.fromPhone,
            },
            { timeout: 5000 }
        );
        logger.info(`[${this.callId}] Registered with Python bridge`);
    }

    // ─── Cleanup ─────────────────────────────────────────────────────────────

    async _cleanup() {
        if (this.audioBridge) {
            await this.audioBridge.stop().catch(() => { });
            this.audioBridge = null;
        }
        if (this.pc) {
            try { this.pc.close(); } catch (e) { /* ignore */ }
            this.pc = null;
        }
        logger.info(`[${this.callId}] Bridge cleaned up`);
    }

    // ─── Start ────────────────────────────────────────────────────────────────

    async start() {
        logger.info(`[${this.callId}] Starting WhatsApp-LiveKit bridge for ${this.fromPhone}`);

        try {
            // Step 1: Register with Python bridge FIRST (before PeerConnection)
            // so that when the audio track arrives, the bridge is already known to Python.
            await this._registerWithPythonBridge();

            // Step 2: Create PeerConnection — ontrack will fire once ICE connects
            await this._createPeerConnection();
            logger.info(`[${this.callId}] PeerConnection created`);

            // Step 3: SDP exchange
            const sdpAnswer = await this._generateSdpAnswer(this.sdpOffer);
            logger.info(`[${this.callId}] SDP answer generated (${sdpAnswer.length} chars)`);

            // Step 4: Send pre-accept to WhatsApp (disabled, as in bugzy-voice)
            // await whatsappService.sendPreAccept(this.callId, this.fromPhone);

            // Step 5: Send SDP answer (accept the call)
            await whatsappService.sendAccept(this.callId, this.fromPhone, sdpAnswer);
            logger.info(`[${this.callId}] Call accepted — SDP answer sent to WhatsApp`);

            // (AudioBridge will be started in pc.ontrack when the audio track arrives)
            logger.info(`[${this.callId}] Bridge initialised — waiting for audio track`);
        } catch (err) {
            logger.error(`[${this.callId}] Bridge start failed`, err);
            await this._cleanup();
            // Notify WhatsApp call failed
            await whatsappService.sendTerminate(this.callId, this.fromPhone).catch(() => { });
            throw err;
        }
    }
}


// ─── Multi-call manager ───────────────────────────────────────────────────────

class BridgeService {
    constructor() {
        this._bridges = {};
    }

    /**
     * Handle an incoming WhatsApp call.
     *
     * @param {string} callId   WhatsApp call ID
     * @param {string} from     Caller phone number
     * @param {string} sdp      SDP offer from WhatsApp
     */
    async handleIncomingCall(callId, from, sdp) {
        logger.info('handleIncomingCall', { callId, from });

        if (this._bridges[callId]) {
            logger.warn('Bridge already exists for call', { callId });
            return;
        }

        // Store callId so we can terminate later
        whatsappService.storeCallId(from, callId);

        // Create LiveKit room
        const roomName = `whatsapp-call-${callId.slice(0, 16)}`;
        try {
            await livekitService.createRoom(roomName);
        } catch (err) {
            logger.error('Failed to create LiveKit room', err);
            await whatsappService.sendTerminate(callId, from).catch(() => { });
            return;
        }

        // Create and start the bridge
        const bridge = new WhatsAppLiveKitBridge(callId, from, sdp, roomName);
        this._bridges[callId] = bridge;

        try {
            await bridge.start();
        } catch (err) {
            logger.error('Bridge start failed', { callId, err });
            delete this._bridges[callId];
        }
    }

    /**
     * Clean up a call (e.g. user hung up or agent terminated).
     *
     * @param {string} callId
     * @param {string} from         Caller phone number (for WhatsApp terminate)
     * @param {boolean} [sendTerminate=true]  Whether to tell WhatsApp to terminate
     */
    async handleCallEnd(callId, from, sendTerminate = true) {
        logger.info('handleCallEnd', { callId, from });

        const bridge = this._bridges[callId];
        if (bridge) {
            await bridge._cleanup().catch(() => { });
            delete this._bridges[callId];
        }

        if (sendTerminate && from) {
            const storedCallId = whatsappService.getCallId(from) || callId;
            await whatsappService.sendTerminate(storedCallId, from).catch((e) => {
                logger.error('sendTerminate failed', e);
            });
            whatsappService.clearCallId(from);
        }

        // Best-effort: delete the LiveKit room
        const roomName = `whatsapp-call-${callId.slice(0, 16)}`;
        await livekitService.deleteRoom(roomName).catch(() => { });

        logger.info('Call ended and cleaned up', { callId });
    }

    getActiveBridgeCount() {
        return Object.keys(this._bridges).length;
    }
}

module.exports = new BridgeService();
