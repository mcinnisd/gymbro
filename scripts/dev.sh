#!/usr/bin/env bash
# ==============================================================================
# GYMBro Unified Development Launcher
# Starts Flask API (Port 5001) + Auto-Tunnel + Expo Frontend (Port 8081)
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPO_DIR="$PROJECT_ROOT/gymbro-frontend-expo"
TUNNEL_FILE="$EXPO_DIR/tunnel.json"

USE_TUNNEL=false
CLEAN_CACHE=false

# Parse command line flags
for arg in "$@"; do
  case $arg in
    --tunnel|-t)
      USE_TUNNEL=true
      shift
      ;;
    --clean|-c)
      CLEAN_CACHE=true
      shift
      ;;
  esac
done

echo "🚀 [GYMBro Dev] Initializing development environment..."
echo "📂 Project root: $PROJECT_ROOT"

# 1. Clean up dangling processes on ports 5001 and 8081
echo "🧹 Checking ports 5001 and 8081..."
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
lsof -ti:8081 | xargs kill -9 2>/dev/null || true

# 2. Start Backend Flask API
echo "🐍 Starting Flask API on port 5001..."
cd "$PROJECT_ROOT"
if [ -d "$PROJECT_ROOT/venv" ]; then
  PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
else
  PYTHON_BIN="python3"
fi

PYTHONPATH="$PROJECT_ROOT" "$PYTHON_BIN" app/main.py &
BACKEND_PID=$!

# Wait for Flask to boot
sleep 2

# Cleanup trap for graceful shutdown
cleanup() {
  echo ""
  echo "🛑 [GYMBro Dev] Shutting down servers..."
  kill -9 $BACKEND_PID 2>/dev/null || true
  if [ -n "$TUNNEL_PID" ]; then
    kill -9 $TUNNEL_PID 2>/dev/null || true
  fi
  lsof -ti:8081 | xargs kill -9 2>/dev/null || true
  lsof -ti:5001 | xargs kill -9 2>/dev/null || true
  echo "👋 Goodbye!"
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 3. Handle Tunnel Mode if requested
if [ "$USE_TUNNEL" = true ]; then
  echo "🌐 [Tunnel Mode] Starting public backend tunnel for port 5001..."
  
  # Try localtunnel with a persistent/custom subdomain or fallback
  SUBDOMAIN="gymbro-api-$(whoami | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
  
  # Start localtunnel in background and capture URL
  npx -y localtunnel --port 5001 --subdomain "$SUBDOMAIN" > /tmp/gymbro_tunnel.log 2>&1 &
  TUNNEL_PID=$!

  # Wait for tunnel URL
  echo "⏳ Waiting for tunnel to establish..."
  TUNNEL_URL=""
  for i in {1..10}; do
    if grep -q "url is:" /tmp/gymbro_tunnel.log 2>/dev/null; then
      TUNNEL_URL=$(grep "url is:" /tmp/gymbro_tunnel.log | awk '{print $NF}')
      break
    fi
    sleep 1
  done

  if [ -z "$TUNNEL_URL" ]; then
    TUNNEL_URL="https://$SUBDOMAIN.loca.lt"
  fi

  echo "✅ Backend Tunnel active at: $TUNNEL_URL"
  echo "{\"tunnel_url\": \"$TUNNEL_URL\"}" > "$TUNNEL_FILE"

  echo "📱 Launching Expo in Tunnel Mode (--tunnel)..."
  cd "$EXPO_DIR"
  if [ "$CLEAN_CACHE" = true ]; then
    npx expo start --tunnel -c
  else
    npx expo start --tunnel
  fi

else
  # LAN / Local Mode
  LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "127.0.0.1")
  echo "📡 [LAN Mode] Backend accessible at: http://$LAN_IP:5001"
  echo "{\"tunnel_url\": \"http://$LAN_IP:5001\"}" > "$TUNNEL_FILE"

  echo "📱 Launching Expo on Local LAN..."
  cd "$EXPO_DIR"
  if [ "$CLEAN_CACHE" = true ]; then
    npx expo start -c
  else
    npx expo start
  fi
fi
