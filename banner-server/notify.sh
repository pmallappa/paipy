#!/usr/bin/env bash
# Send a banner notification to the PAI Banner Server.
# Auto-starts the server if it is not already running.
# Usage: notify.sh '{"message": "...", "type": "phase"}'
set -euo pipefail

PORT=8889
SERVER="$HOME/.claude/banner-server/server.py"

if ! ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
    python3 "$SERVER" &>/dev/null &
    sleep 0.4
fi

curl -s -X POST "http://127.0.0.1:$PORT/notify" \
    -H "Content-Type: application/json" \
    -d "${1:-{\"message\":\"ping\",\"type\":\"info\"}}"
