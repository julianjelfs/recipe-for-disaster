#!/usr/bin/env bash
# Install Recipe for Disaster as an always-on service, reachable over the tailnet.
#
#   - builds the frontend, which the API then serves itself
#   - installs a launchd agent so it starts at login and restarts if it dies
#   - puts `recipes` on your PATH
#   - publishes it to your tailnet over HTTPS with tailscale serve
#
# Safe to re-run.
set -euo pipefail

LABEL="com.julian.recipe-for-disaster"
DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/recipe-for-disaster.log"
PORT=8010
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$HOME/.local/bin"
UV="$(command -v uv)"

echo "==> installing dependencies and building the frontend"
(cd "$ROOT/backend" && uv sync --quiet)
(cd "$ROOT/frontend" && pnpm install --silent && pnpm run build)

echo "==> installing the launchd agent"
mkdir -p "$HOME/Library/LaunchAgents" "$(dirname "$LOG")"
cat > "$PLIST" <<PLIST_BODY
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$UV</string>
    <string>run</string>
    <string>uvicorn</string>
    <string>app.main:app</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT/backend</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$BIN:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_BODY

# An agent still tearing down makes bootstrap fail with a bare I/O error,
# so wait for it to actually go before loading the new one.
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
for _ in $(seq 1 20); do
  launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 || break
  sleep 0.5
done
launchctl bootstrap "$DOMAIN" "$PLIST"

echo "==> putting recipes on your PATH"
mkdir -p "$BIN"
ln -sf "$ROOT/scripts/recipes" "$BIN/recipes"

echo "==> waiting for the service"
for _ in $(seq 1 30); do
  curl -sf -m 1 "http://127.0.0.1:$PORT/api/health" >/dev/null && break
  sleep 0.5
done
curl -sf -m 2 "http://127.0.0.1:$PORT/api/health" >/dev/null \
  || { echo "service did not come up; see $LOG"; exit 1; }

echo "==> publishing to your tailnet"
"$ROOT/scripts/recipes" serve || true

echo
echo "installed. try:  recipes status"
