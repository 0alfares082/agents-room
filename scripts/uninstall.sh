#!/bin/bash
# Removes what scripts/install.sh set up (macOS or Linux). Windows: scripts/uninstall.ps1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
case "$(uname -s)" in
  Darwin)
    LABEL="com.agents-room.board"
    for domain in "gui/$(id -u)" "user/$(id -u)"; do
      launchctl bootout "$domain/$LABEL" 2>/dev/null || true
    done
    rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
    ;;
  Linux)
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user disable --now agents-room.service 2>/dev/null || true
      rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/agents-room.service"
      systemctl --user daemon-reload 2>/dev/null || true
    fi
    rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/agents-room.desktop"
    pkill -f "$ROOT/board/serve.py" 2>/dev/null || true
    ;;
esac
if [ -f "$HOME/.claude/settings.json" ]; then
  python3 - "$ROOT/mod/agents-room" <<'PYMOD'
import json, sys
from pathlib import Path
path = Path.home() / ".claude" / "settings.json"
data = json.loads(path.read_text(encoding="utf-8"))
env = data.get("env", {})
before = [d for d in env.get("CLAUDE_CODE_PLUGIN_DIRS", "").split(":") if d]
dirs = [d for d in before if d != sys.argv[1]]
if dirs != before:  # leave the file untouched when the mod was never added
    if dirs:
        env["CLAUDE_CODE_PLUGIN_DIRS"] = ":".join(dirs)
    else:
        env.pop("CLAUDE_CODE_PLUGIN_DIRS", None)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PYMOD
fi
echo "Agents room removed."
