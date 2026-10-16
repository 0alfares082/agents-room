"""Show mode (?show=1): the same room for a screen recording or a demo, with private words taken out.

Titles stay, with the names in config.json swapped for stand-ins (showAliases, and each
project's showAs). Everything else that carries free text (your asks, Claude's last words,
tool descriptions, ledger goals, PR numbers, session links) is dropped; statuses, timings,
counts, generic tool kinds and check progress stay. The output is built field by field from an
allowlist, so a field added to the board later never reaches show mode by accident.
"""
from __future__ import annotations

import re

import config

WAIT_LINE = "ينطر قرارك"


def _word(name: str) -> re.Pattern:
    # whole word for Latin names (so "Al" never hits "Alpha"), plain match for Arabic
    edge = r"\b" if re.match(r"[A-Za-z0-9]", name) else ""
    return re.compile(edge + re.escape(name) + edge, re.I)


def aliases() -> list[tuple[re.Pattern, str]]:
    pairs = dict(config.CONFIG["showAliases"])
    for p in config.CONFIG["projects"]:
        if p["showAs"] != p["name"]:
            pairs.setdefault(p["name"], p["showAs"])
    # longest first, so "Acme Labs" is swapped before "Acme"
    return [(_word(k), v) for k, v in sorted(pairs.items(), key=lambda kv: -len(kv[0]))]


def leaks() -> re.Pattern | None:
    """Names that must never show: every alias key, plus the keywords of a renamed project."""
    words = set(config.CONFIG["showAliases"])
    for p in config.CONFIG["projects"]:
        if p["showAs"] != p["name"]:
            words.add(p["name"])
            words.update(k for k in p["keywords"] if len(k) >= 3)
    words = {w for w in words if w.strip()}
    if not words:
        return None
    return re.compile("|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)), re.I)


def alias(text: str) -> str:
    for pat, name in aliases():
        text = pat.sub(name, text)
    return text


def safe_title(a: dict, label: str, n: int, leak: re.Pattern | None) -> str:
    if a.get("titled"):
        t = alias(a.get("title", ""))
        if t.strip() and not (leak and leak.search(t)):
            return t
    return f"{label} · مهمة {n}"


def redact(snapshot: dict) -> dict:
    shown_as = {p["name"]: p["showAs"] for p in config.CONFIG["projects"]}
    leak = leaks()
    counter: dict[str, int] = {}
    agents = []
    for a in sorted(snapshot.get("agents", []), key=lambda x: (x.get("startedTs") or "", x["id"])):
        project = a.get("project", config.OTHER)
        label = shown_as.get(project, project)
        counter[label] = counter.get(label, 0) + 1
        st = a["status"]
        led = a.get("ledger") or None
        working = st == "working"
        agents.append({
            "id": a["id"],
            "title": safe_title(a, label, counter[label], leak),
            "titled": True,
            "link": "",
            "summary": "",
            "project": label,
            "tint": config.tint(project),  # a colour, never the name
            "status": st,
            "lastTs": a.get("lastTs", ""),
            "ageS": a.get("ageS", 0),
            "startedTs": a.get("startedTs", ""),
            "ask": "",
            "askTs": "",
            "latest": WAIT_LINE if st == "waiting" else "",
            "latestTs": a.get("latestTs", ""),
            "action": a.get("kind", "") if working else "",
            "actionTs": a.get("actionTs", ""),
            "recent": list(a.get("kinds") or []) if working else [],
            "kind": "",
            "kinds": [],
            "done": [f"انجز {len(a['done'])} بنود"] if a.get("done") else [],
            "waiting": [WAIT_LINE] if st == "waiting" else [],
            "prs": [],
            "ledger": {
                "id": "", "goal": "", "status": led.get("status", ""), "passed": led.get("passed", 0),
                "failed": led.get("failed", 0), "total": led.get("total", 0), "next": "", "park": "",
                "updated": led.get("updated", ""),
            } if led else None,
        })
    order = {a["id"]: i for i, a in enumerate(snapshot.get("agents", []))}
    agents.sort(key=lambda x: order[x["id"]])
    return {
        "generatedAt": snapshot.get("generatedAt"),
        "counts": dict(snapshot.get("counts") or {}),
        "agents": agents,
        "show": True,
    }
