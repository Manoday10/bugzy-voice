/**
 * audio-bridge.js — WebRTC ↔ Python Audio Bridge
 *
 * Captures raw PCM audio from the WhatsApp PeerConnection (via RTCAudioSink)
 * and forwards it to the Python audio_bridge.py server over WebSocket.
 * Return audio from the agent (TTS) arrives via the same WebSocket and is
 * fed back into the PeerConnection (via RTCAudioSource).
 *
 * Adapted from bugzy-voice/app/whatsapp-backend/services/audio-bridge.js
 */

'use strict';

const WebSocket = require('ws');
const logger = require('../utils/logger');

// Port where Python audio_bridge.py WebSocket server listens
const PYTHON_WS_PORT = parseInt(process.env.PYTHON_BRIDGE_PORT || '8001', 10);

class AudioBridge {
    /**
     * @param {string}      callId    WhatsApp call ID (used as WS path)
     * @param {RTCPeerConnection} pc  The WhatsApp-side PeerConnection
     * @param {MediaStreamTrack} audioTrack  The audio track from the caller
     * @param {RTCAudioSource} [returnAudioSource]  Pre-added return audio source (from bridge) — required for agent audio to reach WhatsApp
     */
    constructor(callId, pc, audioTrack, returnAudioSource = null) {
        this.callId = callId;
        this.pc = pc;
        this.audioTrack = audioTrack;
        this.audioSource = returnAudioSource;  // Use pre-created source (track already added to PC before SDP)
        this.pyWs = null;             // WebSocket to Python bridge
        this.audioSink = null;             // RTCAudioSink (captures incoming PCM)
        this.isConnected = false;
        this._reconnectAttempts = 0;
        this._maxReconnectAttempts = 5;
        this._returnBuffer = [];            // Buffer return audio when !audioSource
        this._playbackBuffer = Buffer.alloc(0);
        this._prebufferLogged = false;
        this._playbackStarted = false;
        this._started = false;
    }

    // ─── Connect to Python bridge ──────────────────────────────────────────────

    async connectToPython() {
        logger.info(`[${this.callId}] Connecting to Python audio bridge on port ${PYTHON_WS_PORT}…`);

        return new Promise((resolve, reject) => {
            const wsUrl = `ws://localhost:${PYTHON_WS_PORT}/${this.callId}`;
            const ws = new WebSocket(wsUrl);

            ws.on('open', () => {
                logger.info(`[${this.callId}] WebSocket to Python bridge opened`);
                this.pyWs = ws;
                this.isConnected = true;
                this._reconnectAttempts = 0;

                // Flush any buffered return audio
                if (this._returnBuffer.length > 0) {
                    logger.debug(`[${this.callId}] Flushing ${this._returnBuffer.length} buffered frames`);
                    for (const frame of this._returnBuffer) {
                        this._feedReturnAudio(frame);
                    }
                    this._returnBuffer = [];
                }

                resolve();
            });

            ws.on('message', (data) => {
                // Return audio from Python (agent TTS output)
                if (data instanceof Buffer) {
                    this._feedReturnAudio(data);
                }
            });

            ws.on('error', (err) => {
                logger.error(`[${this.callId}] Python WS error`, err);
                if (!this.isConnected) {
                    reject(err);
                }
            });

            ws.on('close', (code, reason) => {
                logger.warn(`[${this.callId}] Python WS closed`, { code, reason: reason.toString() });
                this.isConnected = false;
                this.pyWs = null;

                // Attempt reconnection
                if (this._started && this._reconnectAttempts < this._maxReconnectAttempts) {
                    this._reconnectAttempts++;
                    const delay = Math.min(1000 * this._reconnectAttempts, 5000);
                    logger.info(`[${this.callId}] Reconnecting in ${delay}ms (attempt ${this._reconnectAttempts})`);
                    setTimeout(() => this.connectToPython().catch(e => logger.error(`[${this.callId}] Reconnect failed`, e)), delay);
                }
            });
        });
    }

    // ─── Return audio (TTS → WhatsApp) ────────────────────────────────────────

    /**
     * Feed raw PCM frames from the Python bridge back into the PeerConnection.
     * Must match bugzy-voice format: samples as Int16Array directly, 48 kHz.
     * Uses prebuffer (30ms) to prevent underruns like bugzy-voice.
     */
    _feedReturnAudio(data) {
        try {
            if (!this.audioSource) {
                this._returnBuffer.push(data);
                return;
            }

            this._playbackBuffer = Buffer.concat([this._playbackBuffer, data]);

            const CHUNK_SIZE = 960;
            const PREBUFFER_SIZE = 960 * 3;
            if (this._playbackBuffer.length < PREBUFFER_SIZE) {
                if (!this._prebufferLogged) {
                    logger.info(`[${this.callId}] Building audio prebuffer (30ms)...`);
                    this._prebufferLogged = true;
                }
                return;
            }
            if (!this._playbackStarted) {
                logger.info(`[${this.callId}] Prebuffer ready, starting playback`);
                this._playbackStarted = true;
            }

            while (this._playbackBuffer.length >= CHUNK_SIZE) {
                const chunk = this._playbackBuffer.subarray(0, CHUNK_SIZE);
                this._playbackBuffer = this._playbackBuffer.subarray(CHUNK_SIZE);
                const samples = new Int16Array(chunk.buffer, chunk.byteOffset, chunk.byteLength / 2);
                const samplesCopy = new Int16Array(samples);

                this.audioSource.onData({
                    samples: samplesCopy,
                    sampleRate: 48000,
                });
            }
        } catch (err) {
            logger.debug(`[${this.callId}] Error feeding return audio`, err);
        }
    }

    // ─── Incoming audio (WhatsApp → Python) ────────────────────────────────────

    /**
     * Set up RTCAudioSink on the caller's track to forward PCM to Python.
     */
    extractAndForwardAudio() {
        if (!this.audioTrack) {
            logger.warn(`[${this.callId}] No audio track — skipping extractAndForwardAudio`);
            return;
        }

        // We need the wrtc module's RTCAudioSink
        let wrtc;
        try {
            wrtc = require('@roamhq/wrtc');
        } catch (e) {
            logger.error(`[${this.callId}] @roamhq/wrtc not available`, e);
            return;
        }

        const { nonstandard } = wrtc;
        const { RTCAudioSink } = nonstandard;
        this.audioSink = new RTCAudioSink(this.audioTrack);

        let frameCount = 0;
        this.audioSink.ondata = ({ samples, sampleRate, channelCount }) => {
            if (!this.pyWs || this.pyWs.readyState !== WebSocket.OPEN) return;

            const pcmBuffer = Buffer.from(samples.buffer || samples);
            try {
                this.pyWs.send(pcmBuffer);
                frameCount++;
                if (frameCount === 1 || frameCount % 500 === 0) {
                    logger.debug(`[${this.callId}] Forwarded ${frameCount} PCM frames to Python`);
                }
            } catch (err) {
                logger.debug(`[${this.callId}] Error sending PCM to Python`, err);
            }
        };

        logger.info(`[${this.callId}] RTCAudioSink attached — forwarding PCM to Python bridge`);
    }

    // ─── Return audio setup ────────────────────────────────────────────────────

    /**
     * Return audio uses the pre-created audioSource (track added to PC before SDP).
     * No setup needed — bridge passes returnAudioSource in constructor.
     */
    _ensureReturnAudioSource() {
        if (this.audioSource) return;
        let wrtc;
        try {
            wrtc = require('@roamhq/wrtc');
        } catch (e) {
            logger.error(`[${this.callId}] @roamhq/wrtc not available for return audio`, e);
            return;
        }
        const { nonstandard } = wrtc;
        const { RTCAudioSource } = nonstandard;
        this.audioSource = new RTCAudioSource();
        const track = this.audioSource.createTrack();
        try {
            this.pc.addTrack(track);
            logger.info(`[${this.callId}] Return audio track added (fallback)`);
        } catch (err) {
            logger.error(`[${this.callId}] Failed to add return audio track`, err);
        }
    }

    // ─── Lifecycle ────────────────────────────────────────────────────────────

    async start() {
        this._started = true;
        logger.info(`[${this.callId}] Starting AudioBridge`);

        this._ensureReturnAudioSource();

        try {
            await this.connectToPython();
            this.extractAndForwardAudio();
            logger.info(`[${this.callId}] AudioBridge started successfully`);
        } catch (err) {
            logger.error(`[${this.callId}] AudioBridge start failed`, err);
            throw err;
        }
    }

    async stop() {
        logger.info(`[${this.callId}] Stopping AudioBridge`);
        this._started = false;

        if (this.audioSink) {
            try { this.audioSink.stop(); } catch (e) { /* ignore */ }
        }
        if (this.pyWs) {
            try { this.pyWs.close(); } catch (e) { /* ignore */ }
            this.pyWs = null;
        }
        this.isConnected = false;
        logger.info(`[${this.callId}] AudioBridge stopped`);
    }
}

module.exports = AudioBridge;
