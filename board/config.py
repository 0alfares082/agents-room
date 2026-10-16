"""Your settings for the agents room, read from config.json beside this file (optional).

Copy config.example.json to config.json and edit it. Every key is optional:

    projects     tag sessions by keywords: [{"name", "keywords", "color", "showAs"}]
    showTitles   show mode keeps session titles (default false: "Project · مهمة 1" instead)
    showAliases  words swapped in those titles in show mode (?show=1): {"Real name": "Stand-in"}
    projectsDir  where Claude Code keeps transcripts (default ~/.claude/projects)
    ledgerDir    folder of <task>/ledger.json files to show check progress (default: none)

Set AGENTS_ROOM_CONFIG to read a config file from somewhere else.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
OTHER = "عام"  # the project tag of a session that matches no keywords
OTHER_COLOR = "#9aa8b8"


def load(path: Path | None = None) -> dict:
    path = path or Path(os.environ.get("AGENTS_ROOM_CONFIG") or HERE / "config.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    projects = []
    for p in data.get("projects") or []:
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        projects.append({
            "name": name,
            "keywords": [str(k).lower() for k in p.get("keywords") or [] if str(k).strip()],
            "color": p.get("color") or OTHER_COLOR,
            "showAs": str(p.get("showAs") or name),
        })
    expand = lambda v: Path(os.path.expanduser(v)) if v else None  # noqa: E731
    return {
        "projects": projects,
        "showTitles": data.get("showTitles") is True,
        "showAliases": {str(k): str(v) for k, v in (data.get("showAliases") or {}).items() if str(k).strip()},
        "projectsDir": expand(data.get("projectsDir")) or Path.home() / ".claude" / "projects",
        "ledgerDir": expand(data.get("ledgerDir")),
    }


CONFIG = load()


def tint(project: str) -> str:
    for p in CONFIG["projects"]:
        if p["name"] == project:
            return p["color"]
    return OTHER_COLOR
