"""Fixture transcripts shaped like ~/.claude/projects/<project>/<session>.jsonl rows."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def iso(seconds_ago: float = 0) -> str:
    t = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def title(name: str, sid: str) -> dict:
    return {"type": "custom-title", "customTitle": name, "sessionId": sid}


def human(text: str, ago: float, entry: str = "claude-desktop") -> dict:
    return {"type": "user", "timestamp": iso(ago), "entrypoint": entry, "isSidechain": False,
            "message": {"role": "user", "content": text}}


def tool_result(ago: float) -> dict:
    return {"type": "user", "timestamp": iso(ago), "entrypoint": "claude-desktop", "isSidechain": False,
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}}


def tool(desc: str, ago: float, name: str = "Bash") -> dict:
    return {"type": "assistant", "timestamp": iso(ago), "entrypoint": "claude-desktop", "isSidechain": False,
            "message": {"role": "assistant", "stop_reason": "tool_use",
                        "content": [{"type": "tool_use", "name": name, "id": "t", "input": {"command": "ls", "description": desc}}]}}


def say(text: str, ago: float, stop: str = "end_turn", entry: str = "claude-desktop") -> dict:
    return {"type": "assistant", "timestamp": iso(ago), "entrypoint": entry, "isSidechain": False,
            "message": {"role": "assistant", "stop_reason": stop, "content": [{"type": "text", "text": text}]}}


def write(folder: Path, sid: str, rows: list[dict]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sid}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def scene(folder: Path) -> dict[str, str]:
    """Four sessions, one per status, plus a headless run that must stay hidden."""
    ids = {
        "working": "aaaaaaaa-0000-0000-0000-000000000001",
        "waiting": "bbbbbbbb-0000-0000-0000-000000000002",
        "done": "cccccccc-0000-0000-0000-000000000003",
        "quiet": "dddddddd-0000-0000-0000-000000000004",
        "headless": "eeeeeeee-0000-0000-0000-000000000005",
    }
    write(folder, ids["working"], [
        title("Acme Room play copies", ids["working"]),
        human("خل الفيديو يشتغل داخل الغرفة", 300),
        say("**خلص**\n- عرفنا السبب\n- قسنا الحجم\n\nالحين ابني المشغل.", 200, stop="tool_use"),
        tool("اشغل اختبارات المشغل", 4),
    ])
    write(folder, ids["waiting"], [
        title("Acme episode two", ids["waiting"]),
        human("Continue with the two episodes.", 900),
        say("الحلقة الاولى خلصت.\n\n**سؤال واحد**\n- **A:** ننطر القواعد اليديدة\n- **B:** نبدا الحين\n\nتبي A ولا B؟", 120),
    ])
    write(folder, ids["done"], [
        title("Globex release", ids["done"]),
        human("deploy it", 1500),
        say("نزل على الموقع وتاكدت منه — كل شي تمام.", 600),
    ])
    write(folder, ids["quiet"], [
        title("Old research", ids["quiet"]),
        human("research this", 9000),
        say("خلصت البحث.", 8000),
    ])
    write(folder, ids["headless"], [
        human("loop run", 60, entry="sdk-py"),
        say("done", 30, entry="sdk-py"),
    ])
    return ids
