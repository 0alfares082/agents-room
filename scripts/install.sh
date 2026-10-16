#!/bin/bash
# Installs the agents room on this Mac:
#   1. a LaunchAgent that keeps the board server running (http://127.0.0.1:8795)
#   2. with --mod, the in-app pane: adds mod/agents-room to Claude Code's mods in ~/.claude/settings.json
# Run it again any time; it replaces its own LaunchAgent. scripts/uninstall.sh removes everything.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.agents-room.board"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGS="$HOME/Library/Logs/agents-room"
PY="$(command -v python3 || true)"

if [ -z "$PY" ]; then
  echo "python3 is missing. Install it first (https://www.python.org or: xcode-select --install)." >&2
  exit 1
fi
"$PY" - <<'PYCHECK'
import sys
if sys.version_info < (3, 9):
    sys.exit(f"python {sys.version.split()[0]} is too old, the board needs 3.9 or newer")
PYCHECK

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
    <string>8795</string>
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

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
sleep 1
# another program on the port would answer the check below and hide a failed start
if lsof -nP -iTCP:8795 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8795 is already used by another program:" >&2
  lsof -nP -iTCP:8795 -sTCP:LISTEN >&2 || true
  echo "Stop it, then run this script again." >&2
  rm -f "$PLIST"
  exit 1
fi
launchctl bootstrap "gui/$(id -u)" "$PLIST"

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fs -o /dev/null http://127.0.0.1:8795/api/board; then break; fi
  sleep 1
done
if curl -fs -o /dev/null http://127.0.0.1:8795/api/board; then
  echo "Board running: http://127.0.0.1:8795/   (show mode: http://127.0.0.1:8795/?show=1)"
else
  echo "The board did not answer. Look at $LOGS/server.err.log" >&2
  exit 1
fi

if [ "${1:-}" = "--mod" ]; then
  "$PY" - "$ROOT/mod/agents-room" <<'PYMOD'
import json, shutil, sys
from pathlib import Path
mod = sys.argv[1]
path = Path.home() / ".claude" / "settings.json"
data = json.loads(path.read_text()) if path.exists() else {}
if path.exists():
    shutil.copy(path, path.with_name("settings.json.bak-agents-room"))
env = data.setdefault("env", {})
dirs = [d for d in env.get("CLAUDE_CODE_PLUGIN_DIRS", "").split(":") if d]
if mod not in dirs:
    dirs.append(mod)
env["CLAUDE_CODE_PLUGIN_DIRS"] = ":".join(dirs)
env["CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"] = "1"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"Mod added to {path} (backup: settings.json.bak-agents-room). Quit and reopen Claude, then type /agents-room")
PYMOD
fi
