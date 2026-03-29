/**
 * server.js — Bugzy WhatsApp Backend Main Entry Point (bugzy-voice parity)
 *
 * Express server that:
 *  - Handles WhatsApp Business webhook events (call initiation, call end)
 *  - Proxies all text/interactive/status webhooks to Python chat API (port 6000)
 *  - Serves /send-meal-plan  (called by Python agent to forward plans via WhatsApp)
 *  - Serves /terminate-call  (called by Python agent to hang up)
 *  - Serves /health          (for monitoring & smoke tests)
 */

'use strict';

// ── WebRTC polyfills — must be loaded BEFORE wrtc/livekit ────────────────────
const wrtc = require('@roamhq/wrtc');
const ws = require('ws');
const { ReadableStream, WritableStream, TransformStream } = require('web-streams-polyfill');
const { TextEncoder, TextDecoder } = require('util');

global.WebSocket = ws;
global.RTCPeerConnection = wrtc.RTCPeerConnection;
global.RTCSessionDescription = wrtc.RTCSessionDescription;
global.RTCIceCandidate = wrtc.RTCIceCandidate;
global.ReadableStream = global.ReadableStream || ReadableStream;
global.WritableStream = global.WritableStream || WritableStream;
global.TransformStream = global.TransformStream || TransformStream;
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

// navigator may be a getter-only property in some Node.js versions
try {
    global.navigator = { userAgent: 'chrome' };
} catch (e) {
    Object.defineProperty(global, 'navigator', {
        value: { userAgent: 'chrome' },
        writable: true,
        configurable: true,
    });
}

try {
    global.window = global;
} catch (e) {
    Object.defineProperty(global, 'window', {
        value: global,
        writable: true,
        configurable: true,
    });
}


// ── Environment ───────────────────────────────────────────────────────────────
require('dotenv').config();
require('dotenv').config({ path: '../.env' });   // Try parent .env as fallback

const express = require('express');
const bridge = require('./services/bridge');
const whatsapp = require('./services/whatsapp');
const logger = require('./utils/logger');

const PORT = parseInt(process.env.PORT || '3000', 10);
const VERIFY_TOKEN = process.env.WHATSAPP_VERIFY_TOKEN || 'my_test_token';
const CHAT_API_PORT = parseInt(process.env.CHAT_API_PORT || '6000', 10);
const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || `http://127.0.0.1:${CHAT_API_PORT}/webhook`;

// Validate critical env vars
const requiredEnv = ['WHATSAPP_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID', 'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET'];
const missingEnv = requiredEnv.filter(k => !process.env[k]);
if (missingEnv.length > 0) {
    logger.warn(`⚠️ Missing env vars: ${missingEnv.join(', ')} — some features may not work`);
} else {
    logger.info('✅ All required environment variables loaded');
}

// ── Express ───────────────────────────────────────────────────────────────────
const app = express();
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

app.use((req, res, next) => {
    logger.info(`${req.method} ${req.originalUrl}`);
    next();
});

// ── Webhook verification (GET) ────────────────────────────────────────────────
app.get('/webhook', (req, res) => {
    const mode = req.query['hub.mode'];
    const token = req.query['hub.verify_token'];
    const challenge = req.query['hub.challenge'];

    if (mode === 'subscribe' && token === VERIFY_TOKEN) {
        logger.info('Webhook verified');
        res.status(200).send(challenge);
    } else {
        logger.warn('Webhook verification failed', { mode, token });
        res.sendStatus(403);
    }
});

// ── Helper: proxy payload to Python chat API ──────────────────────────────────
function proxyToPython(body) {
    const axios = require('axios');
    logger.info(`📨 Proxying webhook to Python backend: ${PYTHON_BACKEND_URL}`);
    axios.post(PYTHON_BACKEND_URL, body, { timeout: 10000 })
        .then(() => logger.info('✅ Successfully proxied webhook to Python'))
        .catch(err => logger.error(`❌ Failed to proxy webhook to Python: ${err.message}`));
}

// ── Webhook events (POST) ─────────────────────────────────────────────────────
app.post('/webhook', async (req, res) => {
    try {
        const body = req.body;
        logger.info('Raw Webhook Body:', JSON.stringify(body, null, 2));

        if (!body.object) {
            return res.sendStatus(404);
        }

        // Acknowledge immediately — WhatsApp requires < 5 s response
        res.sendStatus(200);

        if (!body.entry?.[0]?.changes?.[0]?.value) return;

        const change = body.entry[0].changes[0];
        const value = change.value;
        const field = change.field;

        logger.info(`📥 Webhook field: "${field}"`);

        // ── Voice calls ───────────────────────────────────────────────────────
        if (value.calls && value.calls.length > 0) {
            logger.info('Received Calls Event:', JSON.stringify(value.calls, null, 2));
            const call = value.calls[0];
            const callId = call.id || call.call_id;
            const from = call.from;
            const sdp = call.session?.sdp || call.offer_sdp;

            logger.info('Incoming WhatsApp call', { call_id: callId, from, status: call.status });

            if (sdp) {
                logger.info(`Call Connect: ${callId} from ${from}`);
                bridge.handleIncomingCall(callId, from, sdp)
                    .catch(err => logger.error('handleIncomingCall error', err));
            } else if (call.event === 'terminate' || call.status === 'COMPLETED' || call.status === 'ended') {
                logger.info(`Call ended/terminated: ${callId}`);
                bridge.handleCallEnd(callId, from, false)
                    .catch(err => logger.error('handleCallEnd error', err));
            } else {
                logger.info(`⚠️ Unhandled call event — keys: ${Object.keys(call).join(', ')}`);
            }
        }
        // ── Legacy flat-structure call ────────────────────────────────────────
        else if (value.call_id && value.offer_sdp) {
            logger.info(`Call Connect (legacy flat): ${value.call_id}`);
            bridge.handleIncomingCall(value.call_id, value.from, value.offer_sdp)
                .catch(err => logger.error('handleIncomingCall error', err));
        }
        // ── All other events (messages, statuses, interactive) → Python ───────
        else {
            proxyToPython(body);
        }

    } catch (err) {
        logger.error('Error processing webhook event', err);
        // res.sendStatus already sent above (200), so nothing more to do
    }
});

// ── Send meal/exercise plan via WhatsApp ──────────────────────────────────────
app.post('/send-meal-plan', async (req, res) => {
    const { phone_number, meal_plan, meal_plan_days } = req.body;

    if (!phone_number) {
        return res.status(400).json({ error: 'phone_number required' });
    }

    logger.info('Sending plan to WhatsApp', { phone_number });

    try {
        if (meal_plan_days && Array.isArray(meal_plan_days)) {
            logger.info(`Sending ${meal_plan_days.length} day plans`);
            const sentIds = [];
            for (const [i, dayPlan] of meal_plan_days.entries()) {
                await whatsapp.sendTextMessage(phone_number, dayPlan);
                sentIds.push(i);
                await new Promise(r => setTimeout(r, 1000)); // rate-limit
            }
            logger.info('All day plans sent', { phone_number });
            res.json({ status: 'sent', phone_number, days: sentIds.length });
        } else if (meal_plan) {
            await whatsapp.sendTextMessage(phone_number, typeof meal_plan === 'object' ? JSON.stringify(meal_plan, null, 2) : meal_plan);
            logger.info('Plan sent', { phone_number });
            res.json({ status: 'sent', phone_number });
        } else {
            return res.status(400).json({ error: 'meal_plan or meal_plan_days required' });
        }
    } catch (err) {
        logger.error('Failed to send plan', { phone_number, err: err.message });
        res.status(500).json({ error: 'Failed to send plan', detail: err.message });
    }
});

// ── Terminate call (from Python agent) ───────────────────────────────────────
app.post('/terminate-call', async (req, res) => {
    const { phone_number } = req.body;

    if (!phone_number) {
        return res.status(400).json({ error: 'phone_number required' });
    }

    const callId = whatsapp.getCallId(phone_number);
    if (!callId) {
        logger.warn('No active callId for phone', { phone_number });
        return res.json({ status: 'no_active_call', phone_number });
    }

    logger.info('Terminating call from Python agent', { phone_number, callId });
    try {
        await bridge.handleCallEnd(callId, phone_number, true);
        res.json({ status: 'terminated', phone_number, callId });
    } catch (err) {
        logger.error('Failed to terminate call', { phone_number, err: err.message });
        res.status(500).json({ error: 'Failed to terminate', detail: err.message });
    }
});

// ── Health check ──────────────────────────────────────────────────────────────
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        service: 'bugzy-whatsapp-backend',
        active_calls: bridge.getActiveBridgeCount(),
        timestamp: new Date().toISOString(),
    });
});

// ── Startup ───────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
    logger.info('='.repeat(60));
    logger.info('Bugzy WhatsApp Backend started (bugzy-voice parity)');
    logger.info(`Port:          ${PORT}`);
    logger.info(`Python proxy:  ${PYTHON_BACKEND_URL}`);
    logger.info(`Verify token:  ${VERIFY_TOKEN}`);
    logger.info('='.repeat(60));
});

// ── Graceful shutdown ─────────────────────────────────────────────────────────
process.on('SIGTERM', () => {
    logger.info('SIGTERM received — shutting down gracefully');
    process.exit(0);
});

process.on('uncaughtException', err => {
    logger.error('Uncaught exception', err);
});

process.on('unhandledRejection', reason => {
    logger.error('Unhandled rejection', { reason: String(reason) });
});

module.exports = app;
