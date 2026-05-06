#!/usr/bin/env bash
# start.sh — EZ-catch single-command launcher
# Run with: sudo ./start.sh
# Agent runs as root (needs auditd + iptables).
# Backend and frontend run as the normal user (avoids permission issues).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_DIR/apps/backend"
FRONTEND_DIR="$REPO_DIR/apps/frontend/admin-panel"
AGENT_MAIN="$REPO_DIR/apps/agent/src/main.py"

# ── Detect the real user (not root) ──────────────────────────────────────────
REAL_USER="${SUDO_USER:-allain}"
REAL_HOME=$(eval echo "~$REAL_USER")

# ── Always use the dev-env Python ─────────────────────────────────────────────
DEV_PYTHON="$REAL_HOME/dev-env/bin/python"
if [ ! -x "$DEV_PYTHON" ]; then
    DEV_PYTHON="$(which python3)"
fi
DEV_UVICORN="$REAL_HOME/dev-env/bin/uvicorn"
if [ ! -x "$DEV_UVICORN" ]; then
    DEV_UVICORN="uvicorn"
fi

# ── Colors ────────────────────────────────────────────────────────────────────
GRN='\033[0;32m'; YLW='\033[1;33m'; RED='\033[0;31m'; RST='\033[0m'
info()  { echo -e "${GRN}[start.sh]${RST} $*"; }
warn()  { echo -e "${YLW}[start.sh]${RST} $*"; }
error() { echo -e "${RED}[start.sh]${RST} $*" >&2; }

# ── Root check ────────────────────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run with sudo."
    error "  Usage: sudo ./start.sh"
    exit 1
fi

# ── Kill stale processes on the ports we need ─────────────────────────────────
for port in 3000 8000 8080; do
    fuser -k "$port/tcp" 2>/dev/null || true
done
sleep 0.5

# ── Fix root-owned frontend directories ──────────────────────────────────────
for dir in "$FRONTEND_DIR/node_modules" "$FRONTEND_DIR/.next"; do
    if [ -d "$dir" ]; then
        chown -R "$REAL_USER:users" "$dir" 2>/dev/null || true
    fi
done

# ── PIDs to track ─────────────────────────────────────────────────────────────
PIDS=()

cleanup() {
    info "Shutting down all services..."
    for pid in "${PIDS[@]}"; do
        # Kill the entire process group so grandchildren (node, etc.) also die
        kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    done
    # Extra safety: kill anything still on our ports
    for port in 3000 8000 8080; do
        fuser -k "$port/tcp" 2>/dev/null || true
    done
    info "All services stopped."
    exit 0
}
trap cleanup INT TERM

# ── Logs ──────────────────────────────────────────────────────────────────────
LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"

# ── 1. Backend (runs as normal user) ─────────────────────────────────────────
info "Starting backend (uvicorn on :8000)..."
sudo -u "$REAL_USER" bash -c "cd '$BACKEND_DIR' && '$DEV_UVICORN' src.main:app --host 0.0.0.0 --port 8000 --reload" \
    >"$LOG_DIR/backend.log" 2>&1 &
PIDS+=($!)
sleep 2

# ── 2. Agent (runs as root — needs auditd + iptables) ────────────────────────
info "Starting agent (root, mitmdump + auditd)..."
bash -c "cd '$REPO_DIR' && '$DEV_PYTHON' '$AGENT_MAIN'" \
    >"$LOG_DIR/agent.log" 2>&1 &
PIDS+=($!)
sleep 2

# ── 3. Frontend (runs as normal user) ────────────────────────────────────────
if command -v npm &>/dev/null; then
    info "Starting frontend (Next.js on :3000)..."
    sudo -u "$REAL_USER" bash -c "cd '$FRONTEND_DIR' && npm run dev" \
        >"$LOG_DIR/frontend.log" 2>&1 &
    PIDS+=($!)
    sleep 3
else
    warn "npm not found — skipping frontend."
fi

# ── Status ────────────────────────────────────────────────────────────────────
SEP="────────────────────────────────────────────────────────────────"
echo ""
echo "$SEP"
echo "  EZ-CATCH — all services running"
echo "$SEP"
echo ""
echo "  Backend   → http://localhost:8000/api/v1/logs"
echo "  Dashboard → http://localhost:3000"
echo "  Agent     → logs/agent.log"
echo ""
echo "  PIDs: ${PIDS[*]}"
echo "  Logs: $LOG_DIR/"
echo ""
echo "  Press Ctrl+C to stop everything."
echo "$SEP"
echo ""

# Verify backend is reachable
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q "200"; then
    info "Backend health check: ✓"
else
    warn "Backend health check: might still be starting..."
fi

# Verify frontend is reachable
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null | grep -q "200"; then
    info "Frontend health check: ✓"
else
    warn "Frontend health check: might still be starting (check logs/frontend.log)"
fi

# Wait for children
wait
