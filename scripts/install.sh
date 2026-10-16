#!/bin/bash
# Installs the agents room on macOS or Linux (Windows: scripts/install.ps1):
#   1. keeps the board server running at http://127.0.0.1:8795, also after a restart
#      macOS: a LaunchAgent. Linux: a systemd user service, or an autostart entry when
#      systemd is not available (WSL, containers).
#   2. with --mod (macOS only), the in-app pane: adds mod/agents-room to Claude Code's mods
# Run it again any time; it replaces its own setup. scripts/uninstall.sh removes everything.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT=8795
OS="$(uname -s)"
PY="$(command -v python3 || true)"

if [ -z "$PY" ]; then
  echo "python3 is missing. Install Python 3.9 or newer first (https://www.python.org)." >&2
  exit 1
fi
"$PY" - <<'PYCHECK'
import sys
if sys.version_info < (3, 9):
    sys.exit(f"python {sys.version.split()[0]} is too old, the board needs 3.9 or newer")
PYCHECK

port_busy() {
  "$PY" - "$PORT" <<'PYPORT'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(0)  # busy
sys.exit(1)
PYPORT
}

wait_for_board() {
  for _ in $(seq 1 20); do
    if curl -fs -o /dev/null "http://127.0.0.1:$PORT/api/board"; then return 0; fi
    sleep 1
  done
  return 1
}

refuse_busy_port() {
  # another program on the port would answer the check below and hide a failed start
  if port_busy; then
    echo "Port $PORT is already used by another program. Stop it, then run this script again." >&2
    exit 1
  fi
}

LOGS=""
case "$OS" in
  Darwin)
    LABEL="com.agents-room.board"
    PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
    LOGS="$HOME/Library/Logs/agents-room"
    for domain in "gui/$(id -u)" "user/$(id -u)"; do
      launchctl bootout "$domain/$LABEL" 2>/dev/null || true
    done
    sleep 1
    refuse_busy_port
    mkdir -p "$LOGS" "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$ROOT/board/serve.py</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>15</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$LOGS/server.out.log</string>
  <key>StandardErrorPath</key><string>$LOGS/server.err.log</string>
  <key>EnvironmentVariables</key>
  <dict><key>PYTHONDONTWRITEBYTECODE</key><string>1</string></dict>
</dict>
</plist>
PLISTEOF
    # the GUI domain on a normal login; the user domain on a machine with no GUI session
    launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl bootstrap "user/$(id -u)" "$PLIST"
    ;;
  Linux)
    LOGS="${XDG_STATE_HOME:-$HOME/.local/state}/agents-room"
    UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
    AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/agents-room.desktop"
    mkdir -p "$LOGS"
    if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1 \
        && [ -z "${AGENTS_ROOM_NO_SYSTEMD:-}" ]; then
      systemctl --user disable --now agents-room.service 2>/dev/null || true
      pkill -f "$ROOT/board/serve.py" 2>/dev/null || true
      sleep 1
      refuse_busy_port
      mkdir -p "$UNIT_DIR"
      cat > "$UNIT_DIR/agents-room.service" <<UNITEOF
[Unit]
Description=Agents room board (http://127.0.0.1:$PORT)

[Service]
ExecStart=$PY $ROOT/board/serve.py --port $PORT
WorkingDirectory=$ROOT
Environment=PYTHONDONTWRITEBYTECODE=1
Restart=always
RestartSec=15

[Install]
WantedBy=default.target
UNITEOF
      systemctl --user daemon-reload
      systemctl --user enable --now agents-room.service
      echo "Started as a systemd user service (agents-room.service)."
    else
      pkill -f "$ROOT/board/serve.py" 2>/dev/null || true
      sleep 1
      refuse_busy_port
      mkdir -p "$(dirname "$AUTOSTART")"
      cat > "$AUTOSTART" <<DESKEOF
[Desktop Entry]
Type=Application
Name=Agents room board
Exec=$PY $ROOT/board/serve.py --port $PORT
X-GNOME-Autostart-enabled=true
NoDisplay=true
DESKEOF
      PYTHONDONTWRITEBYTECODE=1 nohup "$PY" "$ROOT/board/serve.py" --port "$PORT" \
        >"$LOGS/server.out.log" 2>"$LOGS/server.err.log" &
      echo "Started in the background; it starts again at your next desktop login (no systemd user session here)."
    fi
    ;;
  *)
    echo "On Windows, run scripts\\install.ps1 in PowerShell instead." >&2
    exit 1
    ;;
esac

if wait_for_board; then
  echo "Board running: http://127.0.0.1:$PORT/   (show mode: http://127.0.0.1:$PORT/?show=1)"
else
  echo "The board did not answer. Look at $LOGS/server.err.log" >&2
  exit 1
fi

if [ "${1:-}" = "--mod" ]; then
  if [ "$OS" != "Darwin" ]; then
    echo "The in-app pane (--mod) is macOS only for now. The browser board works everywhere."
    exit 0
  fi
  "$PY" - "$ROOT/mod/agents-room" <<'PYMOD'
import json, shutil, sys
from pathlib import Path
mod = sys.argv[1]
path = Path.home() / ".claude" / "settings.json"
data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
if path.exists():
    shutil.copy(path, path.with_name("settings.json.bak-agents-room"))
env = data.setdefault("env", {})
dirs = [d for d in env.get("CLAUDE_CODE_PLUGIN_DIRS", "").split(":") if d]
if mod not in dirs:
    dirs.append(mod)
env["CLAUDE_CODE_PLUGIN_DIRS"] = ":".join(dirs)
env["CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"] = "1"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Mod added to {path} (backup: settings.json.bak-agents-room). Quit and reopen Claude, then type /agents-room")
PYMOD
fi
