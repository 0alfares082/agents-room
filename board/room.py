"""The agents room: one animated SVG of a bot per session, plus a short Markdown summary.

Both are built from a board snapshot (board.py). The SVG carries no clock text, so it only
changes when a session changes status or appears, and a surface that redraws it every few
seconds does not restart its animations for nothing. SMIL only, no script: the desktop draws
an interactive Svg in a script-less sandboxed frame.
"""
from __future__ import annotations

import base64
import hashlib
import re
import struct
import time
from datetime import datetime
from html import escape
from pathlib import Path

import config

W = 960
STATUS = {
    "waiting": ("#f2c45a", "ينطرك"),
    "working": ("#5cc8f5", "شغال"),
    "done": ("#6fdcb0", "خلص دوره"),
    "quiet": ("#7d8a99", "هادي"),
}
ARABIC = re.compile(r"[؀-ۿ]")


def short_name(title: str, limit: int = 22) -> str:
    t = title.strip() or title
    if len(t) <= limit:
        return t
    cut = t[:limit].rsplit(" ", 1)[0]
    if len(cut) < 10:
        cut = t[:limit]
    return cut.rstrip(" ,:-") + "…"


def phase(seed: str) -> float:
    return int(hashlib.md5(seed.encode()).hexdigest()[:6], 16) % 3000 / 1000


def text_attrs(s: str) -> str:
    return ' direction="rtl"' if ARABIC.search(s[:6] or "") else ""


DEFS = """<defs>
<radialGradient id="bg" cx="50%" cy="0%" r="90%"><stop offset="0" stop-color="#16263a"/><stop offset="1" stop-color="#0a0f16"/></radialGradient>
<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#132131" stop-opacity="0.2"/><stop offset="1" stop-color="#16283c"/></linearGradient>
<linearGradient id="gHead" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4f8fc"/><stop offset="0.55" stop-color="#c3cfdc"/><stop offset="1" stop-color="#7c8ea4"/></linearGradient>
<linearGradient id="gBody" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e6edf5"/><stop offset="0.6" stop-color="#a9b8c9"/><stop offset="1" stop-color="#66788f"/></linearGradient>
<linearGradient id="gLimb" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#b9c6d4"/><stop offset="1" stop-color="#6b7d93"/></linearGradient>
<linearGradient id="gVisor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#132232"/><stop offset="1" stop-color="#05090e"/></linearGradient>
<filter id="glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="soft" x="-50%" y="-200%" width="200%" height="500%"><feGaussianBlur stdDeviation="5"/></filter>
<filter id="dim"><feColorMatrix type="saturate" values="0.25"/></filter>
</defs>"""


def bot(a: dict, x: float, y: float, s: float) -> str:
    st = a["status"]
    color, word = STATUS[st]
    tint = a.get("tint") or config.tint(a.get("project", ""))
    p = phase(a["id"])
    quiet = st == "quiet"
    bob_amp, bob_dur = (2, 6) if quiet else ((4, 2.4) if st == "working" else (6, 3.4))
    fade = ' opacity="0.62"' if quiet else ""  # outside the f-string: Python 3.9 forbids backslashes there
    out = [f'<g transform="translate({x:.1f} {y:.1f}) scale({s:.3f})"{fade}>']
    out.append('<ellipse cx="0" cy="0" rx="48" ry="11" fill="#000" opacity="0.5" filter="url(#soft)"/>')
    ring_anim = ""
    if st in ("working", "waiting"):
        ring_anim = f'<animate attributeName="opacity" values="0.25;0.9;0.25" dur="{1.2 if st == "waiting" else 2}s" begin="-{p:.2f}s" repeatCount="indefinite"/>'
    out.append(f'<ellipse cx="0" cy="0" rx="42" ry="10" fill="none" stroke="{color}" stroke-width="2.5" opacity="0.7">{ring_anim}</ellipse>')
    out.append(f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -{bob_amp};0 0" dur="{bob_dur}s" begin="-{p:.2f}s" repeatCount="indefinite"/>')
    out.append(f'<ellipse cx="0" cy="-18" rx="17" ry="4" fill="{color}" opacity="0.55" filter="url(#soft)"/>')

    def arm(side: int) -> str:
        if st == "working":
            vals = f"{side * 30};{side * 8};{side * 30}"
            dur = 0.42 + (0.07 if side > 0 else 0)
        elif st == "waiting" and side > 0:
            vals, dur = "150;178;150", 0.9
        elif st == "done":
            vals, dur = f"{side * 14};{side * 20};{side * 14}", 3
        else:
            vals, dur = f"{side * 6};{side * 6}", 4
        return (f'<g transform="translate({side * 35} -82)"><g>'
                f'<animateTransform attributeName="transform" type="rotate" values="{vals}" dur="{dur}s" begin="-{p:.2f}s" repeatCount="indefinite"/>'
                f'<rect x="-7" y="0" width="14" height="40" rx="7" fill="url(#gLimb)"/>'
                f'<circle cx="0" cy="40" r="7" fill="#dfe7f0"/></g></g>')

    out.append(arm(-1))
    out.append(arm(1))
    out.append('<rect x="-31" y="-94" width="62" height="68" rx="24" fill="url(#gBody)"/>')
    out.append('<rect x="-31" y="-94" width="62" height="68" rx="24" fill="none" stroke="#ffffff" stroke-opacity="0.25"/>')
    chest_anim = f'<animate attributeName="opacity" values="1;0.45;1" dur="1.6s" begin="-{p:.2f}s" repeatCount="indefinite"/>' if st != "quiet" else ""
    out.append(f'<circle cx="0" cy="-62" r="7" fill="{color}" filter="url(#glow)">{chest_anim}</circle>')
    out.append('<rect x="-8" y="-104" width="16" height="12" rx="4" fill="#58697e"/>')
    out.append(f'<circle cx="-47" cy="-130" r="8" fill="{tint}"/><circle cx="47" cy="-130" r="8" fill="{tint}"/>')
    out.append('<rect x="-45" y="-162" width="90" height="64" rx="25" fill="url(#gHead)"/>')
    out.append('<rect x="-35" y="-152" width="70" height="44" rx="17" fill="url(#gVisor)"/>')
    out.append('<path d="M-28 -146 q14 -6 30 -3" stroke="#ffffff" stroke-opacity="0.22" stroke-width="3" fill="none" stroke-linecap="round"/>')
    if st == "done":
        out.append(f'<g stroke="{color}" stroke-width="3.5" fill="none" stroke-linecap="round" filter="url(#glow)">'
                   '<path d="M-22 -126 q7 -10 14 0"/><path d="M8 -126 q7 -10 14 0"/></g>')
    elif quiet:
        out.append('<g stroke="#8b99a8" stroke-width="3" stroke-linecap="round"><path d="M-21 -129 h12"/><path d="M9 -129 h12"/></g>')
    else:
        blink = f'<animate attributeName="ry" values="8;8;1;8" keyTimes="0;0.93;0.96;1" dur="{4 + p:.2f}s" repeatCount="indefinite"/>'
        out.append(f'<g fill="{color}" filter="url(#glow)"><ellipse cx="-15" cy="-130" rx="5.5" ry="8">{blink}</ellipse>'
                   f'<ellipse cx="15" cy="-130" rx="5.5" ry="8">{blink}</ellipse></g>')
    out.append('<line x1="0" y1="-162" x2="0" y2="-180" stroke="#93a5ba" stroke-width="3" stroke-linecap="round"/>')
    bulb_anim = "" if quiet else f'<animate attributeName="opacity" values="1;0.3;1" dur="{0.8 if st == "waiting" else 1.8}s" begin="-{p:.2f}s" repeatCount="indefinite"/>'
    out.append(f'<circle cx="0" cy="-184" r="5.5" fill="{color}" filter="url(#glow)">{bulb_anim}</circle>')

    if st == "working":
        out.append(f'<g transform="translate(46 -70) skewY(-8)">'
                   f'<rect x="0" y="-26" width="58" height="40" rx="5" fill="{color}" fill-opacity="0.1" stroke="{color}" stroke-opacity="0.55"/>')
        for i, (w0, w1) in enumerate(((10, 40), (6, 30), (12, 44))):
            out.append(f'<rect x="7" y="{-18 + i * 11}" height="4" rx="2" fill="{color}" opacity="0.8" width="{w0}">'
                       f'<animate attributeName="width" values="{w0};{w1};{w0}" dur="{1.6 + i * 0.4:.1f}s" begin="-{p + i:.2f}s" repeatCount="indefinite"/></rect>')
        out.append('</g>')
    elif st == "waiting":
        out.append(f'<g transform="translate(40 -206)"><animateTransform attributeName="transform" type="translate" values="40 -206;40 -214;40 -206" dur="1.1s" repeatCount="indefinite"/>'
                   f'<rect x="-17" y="-17" width="34" height="30" rx="10" fill="{color}"/><path d="M-6 13 l-4 9 l11 -9 z" fill="{color}"/>'
                   '<text x="0" y="6" text-anchor="middle" font-size="22" font-weight="800" fill="#1a1405" font-family="Tajawal, Geeza Pro, sans-serif">؟</text></g>')
    elif st == "done":
        out.append(f'<g transform="translate(40 -170)"><circle r="11" fill="{color}"/><path d="M-5 0 l3.5 4 l7 -8" stroke="#0b2018" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>')
    else:
        for i in range(2):
            out.append(f'<text x="{30 + i * 10}" y="-176" font-size="{16 - i * 3}" fill="#9fb0c2" font-family="Montserrat, sans-serif" font-weight="700" opacity="0">z'
                       f'<animate attributeName="opacity" values="0;0.9;0" dur="3s" begin="{i * 1.5 - p:.2f}s" repeatCount="indefinite"/>'
                       f'<animateTransform attributeName="transform" type="translate" values="0 0;8 -22" dur="3s" begin="{i * 1.5 - p:.2f}s" repeatCount="indefinite"/></text>')
    out.append('</g>')  # bob

    out.append('</g>')
    name = escape(short_name(a["title"]))
    ly = y + 22 * s
    out.append(f'<text x="{x:.1f}" y="{ly + 14:.1f}" text-anchor="middle" font-size="15" font-weight="700" fill="#eef3f8" font-family="Montserrat, Tajawal, Geeza Pro, sans-serif"{text_attrs(name)}>{name}</text>')
    out.append(f'<text x="{x:.1f}" y="{ly + 32:.1f}" text-anchor="middle" font-size="13" fill="{color}" font-family="Tajawal, Geeza Pro, sans-serif" direction="rtl">{escape(word)} · {escape(a.get("project", ""))}</text>')
    return "".join(out)


REST_MAX = 10  # the back rows show the most recent ones only


def sprite_bot(a: dict, x: float, y: float, s: float, ref: str, w: int, h: int, link: str = "") -> str:
    st = a["status"]
    color, word = STATUS[st]
    p = phase(a["id"])
    quiet = st == "quiet"
    height = 215 * s
    width = height * w / h
    amp, dur = (2, 6) if quiet else ((3, 2.6) if st == "working" else (7, 1.2) if st == "waiting" else (3, 4))
    out = []
    if link:
        out.append(f'<a href="{escape(link)}" target="_top">')
    fade = ' opacity="0.6"' if quiet else ""
    out.append(f'<g transform="translate({x:.1f} {y:.1f})"{fade}>')
    out.append(f'<ellipse cx="0" cy="0" rx="{width * 0.42:.1f}" ry="{9 * s + 4:.1f}" fill="#000" opacity="0.5" filter="url(#soft)"/>')
    ring_anim = f'<animate attributeName="opacity" values="0.2;0.9;0.2" dur="{1.1 if st == "waiting" else 2.2}s" begin="-{p:.2f}s" repeatCount="indefinite"/>' if st in ("working", "waiting") else ""
    out.append(f'<ellipse cx="0" cy="0" rx="{width * 0.4:.1f}" ry="{8 * s + 4:.1f}" fill="none" stroke="{color}" stroke-width="2.5" opacity="0.7">{ring_anim}</ellipse>')
    out.append(f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -{amp};0 0" dur="{dur}s" begin="-{p:.2f}s" repeatCount="indefinite"/>')
    if st == "working":
        out.append(f'<ellipse cx="{width * 0.12:.1f}" cy="{-height * 0.38:.1f}" rx="{width * 0.32:.1f}" ry="{height * 0.16:.1f}" fill="{color}" opacity="0.18" filter="url(#soft)">'
                   f'<animate attributeName="opacity" values="0.1;0.3;0.1" dur="1.8s" begin="-{p:.2f}s" repeatCount="indefinite"/></ellipse>')
    filt = ' filter="url(#dim)"' if quiet else ""
    out.append(f'<use href="#{ref}" x="{-width / 2:.1f}" y="{-height - 6 * s:.1f}" width="{width:.1f}" height="{height:.1f}"{filt}/>')
    top = -height - 6 * s
    if st == "waiting":
        out.append(f'<g transform="translate({width * 0.32:.1f} {top + 6:.1f})"><animateTransform attributeName="transform" type="translate" values="{width * 0.32:.1f} {top + 6:.1f};{width * 0.32:.1f} {top - 2:.1f};{width * 0.32:.1f} {top + 6:.1f}" dur="1.1s" repeatCount="indefinite"/>'
                   f'<rect x="-17" y="-17" width="34" height="30" rx="10" fill="{color}"/><path d="M-6 13 l-4 9 l11 -9 z" fill="{color}"/>'
                   '<text x="0" y="6" text-anchor="middle" font-size="22" font-weight="800" fill="#1a1405" font-family="Tajawal, Geeza Pro, sans-serif">؟</text></g>')
    elif st == "done":
        out.append(f'<g transform="translate({width * 0.34:.1f} {top + height * 0.12:.1f})"><circle r="12" fill="{color}"/><path d="M-5.5 0 l4 4.5 l7.5 -8.5" stroke="#0b2018" stroke-width="2.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>')
    elif quiet:
        for i in range(2):
            out.append(f'<text x="{width * 0.25 + i * 10:.1f}" y="{top + height * 0.15:.1f}" font-size="{16 - i * 3}" fill="#9fb0c2" font-family="Montserrat, sans-serif" font-weight="700" opacity="0">z'
                       f'<animate attributeName="opacity" values="0;0.9;0" dur="3s" begin="{i * 1.5 - p:.2f}s" repeatCount="indefinite"/>'
                       f'<animateTransform attributeName="transform" type="translate" values="0 0;8 -22" dur="3s" begin="{i * 1.5 - p:.2f}s" repeatCount="indefinite"/></text>')
    out.append("</g>")
    name = escape(short_name(a["title"]))
    ly = 22 * s
    out.append(f'<text x="0" y="{ly + 14:.1f}" text-anchor="middle" font-size="15" font-weight="700" fill="#eef3f8" font-family="Montserrat, Tajawal, Geeza Pro, sans-serif"{text_attrs(name)}>{name}</text>')
    out.append(f'<text x="0" y="{ly + 32:.1f}" text-anchor="middle" font-size="13" fill="{color}" font-family="Tajawal, Geeza Pro, sans-serif" direction="rtl">{escape(word)} · {escape(a.get("project", ""))}</text>')
    out.append("</g>")
    if link:
        out.append("</a>")
    return "".join(out)


def layout(agents: list[dict], width: int) -> list[tuple[list[dict], float]]:
    """Rows from back to front: quiet and done at the back, working, then waiting in front."""
    rest = [a for a in agents if a["status"] in ("done", "quiet")]
    groups = [
        (sorted(rest, key=lambda a: a["ageS"])[:REST_MAX][::-1], 0.55, 118),
        ([a for a in agents if a["status"] == "working"], 0.78, 160),
        ([a for a in agents if a["status"] == "waiting"], 0.92, 190),
    ]
    rows = []
    for items, scale, spacing in groups:
        per_row = max(1, int((width - 40) // spacing))
        for i in range(0, len(items), per_row):
            rows.append((items[i:i + per_row], scale))
    return rows


def room_svg(snapshot: dict, width: int = W, size: str = "sm", links: bool = False) -> str:
    import blobs  # the blob room
    return blobs.room(snapshot.get("agents", []), width, links)


def room_svg_bots(snapshot: dict, width: int = W, size: str = "sm", links: bool = False) -> str:
    W = width  # noqa: N806  (the room's own width)
    agents = snapshot.get("agents", [])
    rows = layout(agents, W)
    placed = []
    y = 16.0
    for items, s in rows:
        lift = 26 * s if any(a["status"] == "waiting" for a in items) else 0
        floor_y = y + 224 * s + lift
        n = len(items)
        spacing = min((W - 40) / max(n, 1), 240 * s)
        x0 = W / 2 - spacing * (n - 1) / 2
        for i, a in enumerate(items):
            placed.append((a, x0 + i * spacing, floor_y, s))
        y = floor_y + 22 * s + 44
    height = max(240, int(y + 18))
    top = (placed[0][2] - 40) if placed else 120
    # Characters: one symbol per (character, pose) in use; a missing or over-budget sprite falls back to the drawn bot.
    symbols: dict[str, tuple[str, int, int]] = {}
    chosen: dict[str, str] = {}
    budget = SVG_BUDGET - 30_000 - 1_400 * len(placed)
    for a, _, _, _ in sorted(placed, key=lambda t: ("waiting", "working", "done", "quiet").index(t[0]["status"])):
        name = f"{char_of(a['id'])}-{POSE[a['status']]}"
        if name not in symbols:
            got = sprite(name, size)
            if not got or (size == "sm" and len(got[0]) > budget):
                continue
            symbols[name] = got
            if size == "sm":
                budget -= len(got[0])
        chosen[a["id"]] = name
    sym_defs = "".join(
        f'<symbol id="spr-{n}" viewBox="0 0 {w} {h}"><image width="{w}" height="{h}" href="{href}"/></symbol>'
        for n, (href, w, h) in symbols.items())
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" role="img">', DEFS.replace("</defs>", sym_defs + "</defs>")]
    parts.append(f'<rect width="{W}" height="{height}" fill="url(#bg)"/>')
    parts.append(f'<polygon points="{W * 0.1:.0f},{top:.0f} {W * 0.9:.0f},{top:.0f} {W},{height} 0,{height}" fill="url(#floor)"/>')
    vx, vy = W / 2, top - 260
    lines = []
    for k in range(-6, 7):
        bx = W / 2 + k * (W / 6)
        t = (top - vy) / (height - vy)
        lines.append(f'<line x1="{vx + (bx - vx) * t:.0f}" y1="{top:.0f}" x2="{bx:.0f}" y2="{height}"/>')
    floors = sorted({round(fy) for _, _, fy, _ in placed})
    for fy in floors:
        t = (fy - vy) / (height - vy)
        half = W / 2 * (0.6 + 0.4 * t) * 1.0
        lines.append(f'<line x1="{W / 2 - half:.0f}" y1="{fy}" x2="{W / 2 + half:.0f}" y2="{fy}"/>')
    parts.append(f'<g stroke="#5cc8f5" stroke-opacity="0.07" stroke-width="1">{"".join(lines)}</g>')
    if not placed:
        parts.append(f'<text x="{W / 2}" y="{height / 2}" text-anchor="middle" font-size="22" fill="#9fb0c2" font-family="Tajawal, Geeza Pro, sans-serif" direction="rtl">ما في وكلاء هني الحين</text>')
    for a, x, fy, s in placed:
        name = chosen.get(a["id"])
        link = a.get("link", "") if links else ""
        if name:
            _, w, h = symbols[name]
            parts.append(sprite_bot(a, x, fy, s, f"spr-{name}", w, h, link))
        else:  # no character image yet: a quiet glowing marker, never the old drawn robot
            color = STATUS[a["status"]][0]
            name = escape(short_name(a["title"]))
            parts.append(f'<g transform="translate({x:.1f} {fy:.1f})"><circle cy="{-60 * s:.1f}" r="{18 * s + 6:.1f}" fill="{color}" opacity="0.85" filter="url(#glow)"/>'
                         f'<text y="{22 * s + 14:.1f}" text-anchor="middle" font-size="15" font-weight="700" fill="#eef3f8" font-family="Montserrat, Tajawal, Geeza Pro, sans-serif"{text_attrs(name)}>{name}</text></g>')
    parts.append("</svg>")
    return "".join(parts)


def ago_ar(iso: str, now: float | None = None) -> str:
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return ""
    s = max(0, int((now or time.time()) - t))
    if s < 10:
        return "الحين"
    if s < 60:
        return f"قبل {s} ث"
    m = round(s / 60)
    if m < 60:
        return f"قبل {m} د"
    h = round(m / 60)
    return "قبل ساعة" if h == 1 else f"قبل {h} س"


def md_safe(text: str) -> str:
    return re.sub(r"([\\`*_\[\]<>|#])", r"\\\1", text or "")


def room_markdown(snapshot: dict, now: float | None = None) -> str:
    agents = snapshot.get("agents", [])
    c = snapshot.get("counts", {})
    out = [f"**{c.get('waiting', 0)} ينطرونك · {c.get('working', 0)} شغالين · {c.get('done', 0) + c.get('quiet', 0)} خلصوا او هادين**", ""]
    waiting = [a for a in agents if a["status"] == "waiting"]
    working = [a for a in agents if a["status"] == "working"]
    rest = [a for a in agents if a["status"] in ("done", "quiet")]
    if waiting:
        out.append("### ينطرونك")
        for a in waiting:
            q = (a.get("waiting") or [a.get("latest", "")])[0]
            out.append(f"- **{md_safe(a['title'])}** ({md_safe(a['project'])}، {ago_ar(a.get('latestTs') or a['lastTs'], now)})")
            out.append(f"  {md_safe(q)}")
        out.append("")
    out.append("### شغالين الحين")
    if not working:
        out.append("ما في وكيل شغال الحين.")
    for a in working:
        out.append(f"- **{md_safe(a['title'])}**: {md_safe(a.get('action') or a.get('latest', ''))} ({ago_ar(a.get('actionTs') or a['lastTs'], now)})")
        led = a.get("ledger")
        extra = []
        if a.get("done"):
            extra.append("خلص: " + "، ".join(md_safe(d) for d in a["done"][:2]))
        if led and led.get("total"):
            extra.append(f"الفحوص {led['passed']} من {led['total']}")
        if extra:
            out.append("  " + " · ".join(extra))
    out.append("")
    if rest:
        out.append("### خلصوا وهادين")
        for a in rest[:10]:
            state = "خلص دوره" if a["status"] == "done" else "هادي"
            out.append(f"- **{md_safe(a['title'])}** · {state} · {ago_ar(a['lastTs'], now)}")
    return "\n".join(out).strip() + "\n"


def pane_rows(snapshot: dict, now: float | None = None) -> list[dict]:
    """One short row per agent for the in-app pane: what to show beside its open button."""
    import blobs
    rows = []
    looks = blobs.assign(snapshot.get("agents", []))
    for a in snapshot.get("agents", []):
        st = a["status"]
        if st == "waiting":
            line = (a.get("waiting") or [a.get("latest", "")])[0]
            when = a.get("latestTs") or a["lastTs"]
        elif st == "working":
            line = a.get("action") or a.get("latest", "")
            when = a.get("actionTs") or a["lastTs"]
        else:
            line = a.get("summary") or a.get("latest", "")
            when = a["lastTs"]
        rows.append({
            "id": a["id"], "title": a["title"], "short": short_name(a["title"], 26), "status": st,
            "icon": blobs.icon(a["id"], st, look=looks.get(a["id"])),
            "word": STATUS[st][1], "project": a.get("project", ""), "link": a.get("link", ""),
            "line": line[:220], "ago": ago_ar(when, now),
        })
    return rows


def svg_signature(svg: str) -> str:
    return hashlib.sha1(svg.encode()).hexdigest()[:12]
