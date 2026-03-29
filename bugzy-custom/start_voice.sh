#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start_voice.sh — Start all Bugzy voice services
#
# Usage:
#   chmod +x start_voice.sh
#   ./start_voice.sh
#
# Services started:
#   1. Python audio bridge      (WebSocket + HTTP servers for PCM relay)
#   2. LiveKit agent worker     (Python livekit-agents process)
#   3. Node.js WhatsApp backend (Express server for WebRTC / WhatsApp API)
#
# Prerequisites:
#   • Python venv activated with requirements installed
#   • Node.js 18+ installed
#   • whatsapp-backend/.env configured (copy from .env.template)
#   • bugzy-custom/.env configured with LIVEKIT_* and DEEPGRAM_API_KEY vars
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "======================================================"
echo " Bugzy Voice Services Startup"
echo " $(date)"
echo "======================================================"

# ── 0. Validate environment ────────────────────────────────────────────────────
check_env() {
    local var="$1"
    if [ -z "${!var}" ]; then
        echo "ERROR: Environment variable $var is not set."
        echo "       Check $SCRIPT_DIR/.env"
        exit 1
    fi
}

if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a; source "$SCRIPT_DIR/.env"; set +a
fi

# Google Cloud TTS — use service account key (override via .env if needed)
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -f "$SCRIPT_DIR/app/services/voice/bugzy-voice-79d576b7d7b0.json" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$SCRIPT_DIR/app/services/voice/bugzy-voice-79d576b7d7b0.json"
fi

check_env LIVEKIT_URL
check_env LIVEKIT_API_KEY
check_env LIVEKIT_API_SECRET
check_env DEEPGRAM_API_KEY

# ── 0b. Kill any stale processes on our ports ──────────────────────────────────
echo "► Clearing any stale processes on ports 8001, 9001, 3000, 8081..."
lsof -ti:8001,9001,3000,8081 | xargs kill -9 2>/dev/null || true
sleep 1
echo "  [OK] Ports cleared"
echo ""

echo "[OK] Environment variables validated"

# ── Set PYTHONPATH so all Python services can import 'app' ────────────────────
export PYTHONPATH="$SCRIPT_DIR"

if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
elif [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# ── 1. Python Audio Bridge ─────────────────────────────────────────────────────
echo ""
echo "► Starting Python audio bridge..."
python3 -m app.services.voice.audio_bridge \
    > "$LOG_DIR/audio_bridge.log" 2>&1 &
BRIDGE_PID=$!
echo "  PID: $BRIDGE_PID  (logs: $LOG_DIR/audio_bridge.log)"

# Give the bridge a moment to start
sleep 2
if ! kill -0 $BRIDGE_PID 2>/dev/null; then
    echo "ERROR: Audio bridge failed to start. Check $LOG_DIR/audio_bridge.log"
    exit 1
fi
echo "  [OK] Audio bridge running"

# ── 2. LiveKit Agent Worker ────────────────────────────────────────────────────
echo ""
echo "► Starting LiveKit agent worker..."
python3 -m app.services.voice.livekit_agent start \
    > "$LOG_DIR/livekit_agent.log" 2>&1 &
AGENT_PID=$!
echo "  PID: $AGENT_PID  (logs: $LOG_DIR/livekit_agent.log)"

sleep 3
if ! kill -0 $AGENT_PID 2>/dev/null; then
    echo "ERROR: LiveKit agent failed to start. Check $LOG_DIR/livekit_agent.log"
    kill $BRIDGE_PID 2>/dev/null || true
    exit 1
fi
echo "  [OK] LiveKit agent worker running"

# ── 3. Node.js WhatsApp Backend ────────────────────────────────────────────────
echo ""
echo "► Starting Node.js WhatsApp backend..."
cd "$SCRIPT_DIR/whatsapp-backend"

# Install dependencies if node_modules is missing
if [ ! -d "node_modules" ]; then
    echo "  Installing Node.js dependencies..."
    npm install --silent
fi

node server.js \
    > "$LOG_DIR/whatsapp_backend.log" 2>&1 &
NODE_PID=$!
echo "  PID: $NODE_PID  (logs: $LOG_DIR/whatsapp_backend.log)"

sleep 2
if ! kill -0 $NODE_PID 2>/dev/null; then
    echo "ERROR: Node.js backend failed to start. Check $LOG_DIR/whatsapp_backend.log"
    kill $BRIDGE_PID $AGENT_PID 2>/dev/null || true
    exit 1
fi
echo "  [OK] Node.js WhatsApp backend running"

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo " All Bugzy voice services are running!"
echo "======================================================"
echo " Audio Bridge    PID: $BRIDGE_PID  port: 8001 (WS) / 9001 (HTTP)"
echo " LiveKit Agent   PID: $AGENT_PID"
echo " WhatsApp Backend PID: $NODE_PID  port: 3000"
echo ""
echo " Health check: curl http://localhost:3000/health"
echo " Stop all:     kill $BRIDGE_PID $AGENT_PID $NODE_PID"
echo "======================================================"

# Trap Ctrl+C to kill all services
trap "echo ''; echo 'Stopping all voice services…'; kill $BRIDGE_PID $AGENT_PID $NODE_PID 2>/dev/null || true; exit 0" INT TERM

# Keep script alive
wait
