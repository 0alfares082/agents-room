#!/bin/bash
# Removes the board's LaunchAgent and the mod entry that scripts/install.sh added.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.agents-room.board"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
python3 - "$ROOT/mod/agents-room" <<'PYMOD'
import json, sys
from pathlib import Path
path = Path.home() / ".claude" / "settings.json"
if path.exists():
    data = json.loads(path.read_text())
    env = data.get("env", {})
    dirs = [d for d in env.get("CLAUDE_CODE_PLUGIN_DIRS", "").split(":") if d and d != sys.argv[1]]
    if dirs:
        env["CLAUDE_CODE_PLUGIN_DIRS"] = ":".join(dirs)
    else:
        env.pop("CLAUDE_CODE_PLUGIN_DIRS", None)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
PYMOD
echo "Agents room removed."
