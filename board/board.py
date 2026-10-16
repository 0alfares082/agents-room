#!/usr/bin/env python3
"""Agents board snapshot: every recent Claude Code session on this Mac, read from its transcript.

Deterministic, stdlib only. Reads ~/.claude/projects/<project>/<session>.jsonl incrementally
(new bytes only after the first read), plus optional task ledgers (config.py), and returns one
JSON snapshot per call. Nothing is written back to the transcripts.

    python3 board/board.py            # print one snapshot as JSON
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from config import CONFIG, OTHER  # noqa: E402

PROJECTS_DIR = CONFIG["projectsDir"]
LEDGER_DIR = CONFIG["ledgerDir"]
APP_SESSIONS_DIR = Path.home() / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
APP_LINK = "claude://claude.ai/epitaxy/"

WINDOW_S = 12 * 3600          # sessions older than this are not shown
FIRST_READ_BYTES = 4_000_000  # a first read starts this far from the end of a long transcript
WORKING_S = 600               # a turn still open after this long reads as quiet, not working
DONE_S = 45 * 60              # a finished turn this recent reads as "just finished"
WAITING_S = 6 * 3600          # a question left this long reads as quiet
SHOWN_ENTRYPOINTS = {"claude-desktop", "cli"}

HAMZA = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا"})
DASHES = re.compile(r"\s*[—–]\s*")
MD_NOISE = re.compile(r"(\*\*|__|`|^#+\s*|^\s*>\s?)", re.M)


ACTION_NAMES = {
    "Read": "يقرا ملف", "Edit": "يعدل ملف", "Write": "يكتب ملف", "Grep": "يدور بالكود",
    "Glob": "يدور ملفات", "Agent": "مشغل وكيل مساعد", "SendMessage": "يراسل قعدة ثانية",
    "Skill": "يشغل مهارة", "ToolSearch": "يجهز ادوات", "WebFetch": "يقرا صفحة",
    "WebSearch": "يبحث بالنت", "TaskStop": "يوقف شغل", "AskUserQuestion": "يسالك",
}

DONE_HEAD = re.compile(r"(خلص|انسوى|اللي انسوى|تم|نجح|صار|شغال الحين|انتشر|اندمج)")
WAIT_HEAD = re.compile(r"(ينطرك|عليك|الباقي عليك|ناطر|سؤال|جوابك|قرارك|تبي)")
QUESTION = re.compile(r"(؟|\?\s*$|^\s*[-*]?\s*\**[A-D]\**\s*[:).]|تبي\s|توافق|قول لي|ردك|كلمتك|جوابك)", re.M)
NOT_HUMAN = ("<", "Another Claude session", "Stop hook feedback", "[Request interrupted",
             "Base directory for this skill", "Caveat:", "This session is being continued")


def clean(text: str, limit: int | None = None) -> str:
    """Strip markdown marks, hamza on alef and long dashes; optionally cut at a word."""
    text = MD_NOISE.sub("", text or "").translate(HAMZA)
    text = DASHES.sub("، ", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    if limit and len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = cut.rstrip("،,.:؛ ") + "…"
    return text


def first_lines(text: str, n: int = 2, limit: int = 220) -> str:
    lines = [clean(l) for l in (text or "").splitlines()]
    lines = [l for l in lines if l and not l.startswith("|") and l not in ("---",)]
    return clean(" ".join(lines[:n]), limit)


def bullets_under(text: str, head: re.Pattern, limit: int = 4) -> list[str]:
    """Bullet lines that sit under a heading line matching head (sessions write **خلص** etc.)."""
    out: list[str] = []
    active = False
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        bullet = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)", line)
        if bullet and active:
            item = clean(bullet.group(1), 140)
            if item:
                out.append(item)
            if len(out) >= limit:
                break
        elif not bullet:
            is_head = (line.startswith("**") and len(line) < 80) or line.startswith("#") or (line.endswith(":") and len(line) < 60)
            if is_head:
                active = bool(head.search(line))
            elif len(line) > 80:
                active = False
    return out


class SessionState:
    __slots__ = ("sid", "path", "offset", "rest", "title", "entrypoint", "first_ts", "last_ts",
                 "last_ask", "last_ask_ts", "texts", "actions", "kinds", "turn_open", "last_assistant_ts",
                 "end_turn_ts", "prs", "human_after_text", "cwd", "last_uuid")

    def __init__(self, sid: str, path: Path):
        self.sid, self.path = sid, path
        self.offset, self.rest = 0, b""
        self.title = ""
        self.entrypoint = ""
        self.first_ts = self.last_ts = ""
        self.last_ask = ""
        self.last_ask_ts = ""
        self.texts: list[tuple[str, str]] = []
        self.actions: list[tuple[str, str]] = []
        self.kinds: list[str] = []  # generic word per action, for show mode
        self.turn_open = False
        self.last_assistant_ts = ""
        self.end_turn_ts = ""
        self.prs: list[str] = []
        self.human_after_text = False
        self.cwd = ""
        self.last_uuid = ""


def human_text(content) -> str:
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    else:
        return ""
    text = text.strip()
    if not text or text.startswith(NOT_HUMAN):
        return ""
    text = re.sub(r"<pasted_content[^>]*>", "", text).replace("</pasted_content>", "")
    return re.sub(r"</?pasted_content[^>]*>", "", text).strip()


def action_label(block: dict) -> str:
    name = block.get("name", "")
    inp = block.get("input") or {}
    for key in ("description", "summary", "action_summary"):
        val = inp.get(key)
        if isinstance(val, str) and val.strip():
            return clean(val, 120)
    if name.startswith("mcp__"):
        if "list_events" in name or "search_session" in name:
            return "يقرا قعدة ثانية"
        if "send_message" in name:
            return "يراسل قعدة ثانية"
        if "Browser" in name or "chrome" in name:
            return "يشتغل بالمتصفح"
        return "يستخدم اداة خارجية"
    return ACTION_NAMES.get(name, name)


def action_kind(block: dict) -> str:
    """The tool's kind in generic words, with nothing from its input (show mode)."""
    name = block.get("name", "")
    if name == "Bash":
        return "يشغل امر"
    if name.startswith("mcp__"):
        if "Browser" in name or "chrome" in name:
            return "يشتغل بالمتصفح"
        if "list_events" in name or "search_session" in name:
            return "يقرا قعدة ثانية"
        if "send_message" in name:
            return "يراسل قعدة ثانية"
        if "update_plan" in name or "wrap_up" in name:
            return "يرتب الخطة"
        return "يستخدم اداة خارجية"
    return ACTION_NAMES.get(name, "يشتغل")


def apply_row(st: SessionState, e: dict) -> None:
    typ = e.get("type")
    ts = e.get("timestamp") or ""
    if typ == "custom-title" and e.get("customTitle"):
        st.title = e["customTitle"]
    elif typ == "agent-name" and e.get("agentName") and not st.title:
        st.title = e["agentName"]
    if e.get("entrypoint"):
        st.entrypoint = e["entrypoint"]
    if e.get("cwd") and not st.cwd:
        st.cwd = e["cwd"]
    if ts:
        st.first_ts = st.first_ts or ts
        if ts > st.last_ts:
            st.last_ts = ts
    if e.get("isSidechain"):
        return
    if typ == "user":
        content = (e.get("message") or {}).get("content")
        text = human_text(content)
        if text:
            st.last_ask, st.last_ask_ts = text, ts
            st.human_after_text = True
        st.turn_open = True
    elif typ == "attachment":
        att = e.get("attachment") or {}
        if att.get("type") == "queued_command" and (att.get("origin") or {}).get("kind") == "human":
            text = human_text(att.get("prompt"))
            if text:
                st.last_ask, st.last_ask_ts = text, ts
                st.human_after_text = True
    elif typ == "assistant":
        msg = e.get("message") or {}
        st.last_assistant_ts = ts
        st.last_uuid = e.get("uuid") or st.last_uuid
        for block in msg.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and block.get("text", "").strip():
                st.texts.append((ts, block["text"]))
                st.texts = st.texts[-12:]
                st.human_after_text = False
                for pr in re.findall(r"github\.com/[\w.-]+/[\w.-]+/pull/\d+", block["text"]):
                    if pr not in st.prs:
                        st.prs = (st.prs + [pr])[-4:]
            elif block.get("type") == "tool_use":
                st.actions.append((ts, action_label(block)))
                st.actions = st.actions[-15:]
                st.kinds = (st.kinds + [action_kind(block)])[-15:]
        stop = msg.get("stop_reason")
        if stop == "end_turn":
            st.turn_open = False
            st.end_turn_ts = ts
        elif stop == "tool_use":
            st.turn_open = True


def read_new(st: SessionState) -> None:
    try:
        size = st.path.stat().st_size
    except OSError:
        return
    if size < st.offset:  # rewritten: start over
        st.__init__(st.sid, st.path)
    if size == st.offset:
        return
    with st.path.open("rb") as fh:
        start = st.offset
        if start == 0 and size > FIRST_READ_BYTES:
            start = size - FIRST_READ_BYTES
            fh.seek(start)
            fh.readline()  # drop the partial first line
            start = fh.tell()
        else:
            fh.seek(start)
        data = st.rest + fh.read(size - start)
    st.offset = size
    lines = data.split(b"\n")
    st.rest = lines.pop()  # last piece may be a half-written line
    for raw in lines:
        if not raw.strip():
            continue
        try:
            apply_row(st, json.loads(raw))
        except (ValueError, TypeError, AttributeError):
            continue


def parse_ts(ts: str) -> float:
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def project_of(*texts: str) -> str:
    hay = " ".join(t for t in texts if t).lower()
    for p in CONFIG["projects"]:
        if any(k in hay for k in p["keywords"]):
            return p["name"]
    return OTHER


def load_ledgers() -> dict[str, list[dict]]:
    """Map session id prefix (8 chars) -> ledgers bound to it."""
    by_sid: dict[str, list[dict]] = {}
    if not LEDGER_DIR or not LEDGER_DIR.is_dir():
        return by_sid
    cutoff = time.time() - 3 * 86400
    for path in LEDGER_DIR.glob("*/ledger.json"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
            led = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        checks = led.get("checks") or {}
        passed = sum(1 for c in checks.values() if (c.get("last") or {}).get("ok"))
        failed = sum(1 for c in checks.values() if (c.get("last") or {}).get("ok") is False)
        item = {
            "id": led.get("id", path.parent.name),
            "goal": clean(led.get("goal", ""), 160),
            "status": led.get("status", ""),
            "passed": passed,
            "failed": failed,
            "total": len(checks),
            "next": clean(led.get("next") or "", 160),
            "park": clean(led.get("park_reason") or "", 160),
            "updated": led.get("updated", ""),
        }
        for s in led.get("sessions") or []:
            sid = (s.get("id") or "")[:8]
            if sid:
                by_sid.setdefault(sid, []).append(item)
    return by_sid


def load_app_sessions(folder: Path | None = None) -> dict[str, dict]:
    """The desktop app's own session records: transcript id -> link, title, archive flag, summary."""
    folder = folder or APP_SESSIONS_DIR
    out: dict[str, dict] = {}
    if not folder.is_dir():
        return out
    cutoff = time.time() - 2 * 86400
    for path in folder.glob("*/*/local_*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
            d = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cli = d.get("cliSessionId")
        if not cli:
            continue
        summ = d.get("postTurnSummary") or {}
        out[cli] = {
            "cwd": d.get("cwd") or "",
            "localId": d.get("sessionId", path.stem),
            "title": d.get("title") or "",
            "archived": bool(d.get("isArchived")),
            "category": summ.get("status_category") or "",
            "detail": clean(summ.get("status_detail") or "", 160),
            "needs": clean(summ.get("needs_action") or "", 200),
            "summaryFor": d.get("postTurnSummaryFor") or "",
        }
    return out


def session_view(st: SessionState, ledgers: list[dict], now: float, app: dict | None = None) -> dict:
    last = max(parse_ts(st.last_ts), 0.0)
    try:
        last = max(last, st.path.stat().st_mtime) if st.turn_open else last
    except OSError:
        pass
    age = now - last if last else 1e9
    last_text_ts, last_text = st.texts[-1] if st.texts else ("", "")
    asks = bool(last_text) and not st.human_after_text and bool(QUESTION.search(last_text[-700:]))
    if st.turn_open and age < WORKING_S:
        status = "working"
    elif not st.turn_open and asks and age < WAITING_S:
        status = "waiting"
    elif not st.turn_open and age < DONE_S:
        status = "done"
    else:
        status = "quiet"

    done: list[str] = []
    waiting: list[str] = []
    for _, text in reversed(st.texts[-4:]):
        if not done:
            done = bullets_under(text, DONE_HEAD)
        if not waiting:
            waiting = bullets_under(text, WAIT_HEAD, 3)
        if done and waiting:
            break
    if status == "waiting" and not waiting and last_text:
        qs = [clean(l, 160) for l in last_text.splitlines() if QUESTION.search(l)]
        waiting = [q for q in qs if q][:3]
    if status != "waiting":
        waiting = waiting if any(l.get("status") == "parked" for l in ledgers) else []

    app = app or {}
    fresh = bool(app.get("summaryFor")) and app.get("summaryFor") == st.last_uuid
    if fresh and not st.turn_open:
        if app.get("category") == "blocked" and app.get("needs") and age < WAITING_S:
            status = "waiting"
            waiting = [app["needs"]] + [w for w in waiting if w != app["needs"]][:2]
        elif app.get("category") in ("completed", "review_ready") and status == "waiting" and not app.get("needs"):
            status = "done" if age < DONE_S else "quiet"
            waiting = []

    open_ledgers = [l for l in ledgers if l["status"] in ("active", "parked")]
    lead = sorted(open_ledgers or ledgers, key=lambda l: l["updated"], reverse=True)[:1]
    action_ts, action = st.actions[-1] if st.actions else ("", "")
    return {
        "id": st.sid,
        "title": clean(app.get("title") or st.title, 90) or first_lines(st.last_ask, 1, 90) or "قعدة بدون اسم",
        "titled": bool(clean(app.get("title") or st.title, 90)),  # False: the title is the user's own words
        "link": APP_LINK + app["localId"] if app.get("localId") else "",
        "summary": app.get("detail", "") if fresh else "",
        "project": project_of(st.title, st.last_ask[:400], " ".join(l["goal"] for l in ledgers)),
        "status": status,
        "lastTs": st.last_ts,
        "ageS": int(age),
        "startedTs": st.first_ts,
        "ask": first_lines(st.last_ask, 2, 200),
        "askTs": st.last_ask_ts,
        "latest": first_lines(last_text, 3, 320),
        "latestTs": last_text_ts,
        "action": action,
        "actionTs": action_ts,
        "recent": [a for _, a in st.actions[-4:-1]][::-1],
        "kind": st.kinds[-1] if st.kinds else "",
        "kinds": st.kinds[-4:-1][::-1],
        "done": done,
        "waiting": waiting,
        "prs": st.prs,
        "ledger": lead[0] if lead else None,
    }


class Board:
    """Keeps parsed state per transcript between calls; thread safe."""

    def __init__(self, projects_dir: Path = PROJECTS_DIR, window_s: int = WINDOW_S):
        self.projects_dir = projects_dir
        self.window_s = window_s
        self.states: dict[str, SessionState] = {}
        self.lock = threading.Lock()
        self._ledgers: tuple[float, dict] = (0.0, {})
        self._app: tuple[float, dict] = (0.0, {})
        self.app_dir = None  # None: the app's real folder; False: none (tests); a Path: that folder

    def app_sessions(self) -> dict:
        at, data = self._app
        if self.app_dir is False:
            return {}
        if time.time() - at > 3:
            data = load_app_sessions(self.app_dir)
            self._app = (time.time(), data)
        return data

    def ledgers(self) -> dict:
        at, data = self._ledgers
        if time.time() - at > 5:
            data = load_ledgers()
            self._ledgers = (time.time(), data)
        return data

    def snapshot(self, now: float | None = None) -> dict:
        now = now or time.time()
        with self.lock:
            seen = set()
            apps = self.app_sessions()
            # a single project folder (tests) or the whole projects root, one folder per project
            paths = {p.stem: p for pat in ("*.jsonl", "*/*.jsonl") for p in self.projects_dir.glob(pat)}
            if self.app_dir is not False:  # sessions the app opened in other folders (worktrees, other repos)
                for cli, app in apps.items():
                    if cli not in paths and app.get("cwd") and not app["archived"]:
                        cand = self.projects_dir.parent / re.sub(r"[^A-Za-z0-9-]", "-", app["cwd"]) / f"{cli}.jsonl"
                        if cand.is_file():
                            paths[cli] = cand
            for sid, path in paths.items():
                try:
                    if now - path.stat().st_mtime > self.window_s:
                        continue
                except OSError:
                    continue
                seen.add(sid)
                st = self.states.get(sid)
                if st is None:
                    st = self.states[sid] = SessionState(sid, path)
                read_new(st)
            for sid in list(self.states):
                if sid not in seen:
                    del self.states[sid]
            ledgers = self.ledgers()
            agents = []
            for st in self.states.values():
                if st.entrypoint and st.entrypoint not in SHOWN_ENTRYPOINTS:
                    continue
                if not (st.title or st.last_ask):
                    continue
                app = apps.get(st.sid)
                if app and app["archived"]:
                    continue
                agents.append(session_view(st, ledgers.get(st.sid[:8], []), now, app))
        order = {"waiting": 0, "working": 1, "done": 2, "quiet": 3}
        agents.sort(key=lambda a: a["ageS"])
        kept, titles = [], set()
        for a in agents:  # after /clear the same session continues in a new transcript
            if a["title"] in titles and a["status"] in ("done", "quiet"):
                continue
            titles.add(a["title"])
            kept.append(a)
        agents = sorted(kept, key=lambda a: (order[a["status"]], a["ageS"]))
        counts = {k: sum(1 for a in agents if a["status"] == k) for k in order}
        return {
            "generatedAt": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"),
            "counts": counts,
            "agents": agents,
        }


if __name__ == "__main__":
    print(json.dumps(Board().snapshot(), ensure_ascii=False, indent=2))
