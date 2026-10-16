"""Blob characters: one flat coloured shape with two white eyes per session
(round, cloud, triangle, drop and rounded-square blobs piled together).

Colour and shape say WHO (stable per session id); eyes, motion and one small badge say the STATE:
working = eyes on the work and a typing bubble, waiting = big eyes, a hop and a "؟",
done = happy eyes and a check, quiet = closed eyes, slow breathing and a "z". SMIL only, no script.
"""
from __future__ import annotations

import hashlib
from html import escape

COLORS = ["#ff6a13", "#ff9f0a", "#12b5a5", "#9b5cff", "#1a7cff", "#ff2d95", "#a0663f", "#8b8b8b",
          "#22c55e", "#ef4444", "#06b6d4", "#d946ef", "#84cc16", "#f472b6", "#facc15", "#6366f1"]
SHAPES = ["circle", "squircle", "cloud", "triangle", "drop", "tall", "bean"]
STATE_COLOR = {"waiting": "#f5c04a", "working": "#6cb6ff", "done": "#4ade80", "quiet": "#a8a29e"}
STAGE_IN, STAGE_OUT = "#35332f", "#262624"  # Claude's dark warm grey, smooth from centre to edge
STATE_WORD = {"waiting": "ينطرك", "working": "شغال", "done": "خلص دوره", "quiet": "هادي"}


def _h(sid: str, salt: str) -> int:
    return int(hashlib.md5((salt + sid).encode()).hexdigest()[:8], 16)


def identity(sid: str) -> tuple[str, str]:
    """(colour, shape) for a session: stable, so a session keeps its look between visits."""
    return COLORS[_h(sid, "c") % len(COLORS)], SHAPES[_h(sid, "s") % len(SHAPES)]


def assign(agents: list[dict]) -> dict[str, tuple[str, str]]:
    """Distinct colour (and a varied shape) for every visible session; stable while the same sessions are up."""
    out: dict[str, tuple[str, str]] = {}
    used_c: set[str] = set()
    used_s: dict[str, int] = {}
    for a in sorted(agents, key=lambda a: a["id"]):
        ci = _h(a["id"], "c") % len(COLORS)
        for k in range(len(COLORS)):
            c = COLORS[(ci + k) % len(COLORS)]
            if c not in used_c or len(used_c) >= len(COLORS):
                break
        used_c.add(c)
        si = _h(a["id"], "s") % len(SHAPES)
        shape = min((SHAPES[(si + k) % len(SHAPES)] for k in range(len(SHAPES))), key=lambda sh: used_s.get(sh, 0))
        used_s[shape] = used_s.get(shape, 0) + 1
        out[a["id"]] = (c, shape)
    return out


def body(shape: str, r: float, color: str) -> tuple[str, float]:
    """The shape with its bottom on y=0, and the y of its eyes."""
    f = f'fill="{color}"'
    if shape == "circle":
        return f'<circle cx="0" cy="{-r:.1f}" r="{r:.1f}" {f}/>', -1.05 * r
    if shape == "squircle":
        return (f'<rect x="{-r:.1f}" y="{-2 * r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}" rx="{0.42 * r:.1f}" {f} '
                f'transform="rotate(-9 0 {-r:.1f})"/>'), -1.08 * r
    if shape == "tall":
        return (f'<rect x="{-0.9 * r:.1f}" y="{-2.1 * r:.1f}" width="{1.8 * r:.1f}" height="{2.1 * r:.1f}" rx="{0.36 * r:.1f}" {f} '
                f'transform="rotate(10 0 {-r:.1f})"/>'), -1.2 * r
    if shape == "cloud":
        parts = [(-0.52, -0.62, 0.62), (0.5, -0.64, 0.64), (-0.18, -1.2, 0.62), (0.34, -1.12, 0.56), (0, -0.55, 0.58)]
        circles = "".join(f'<circle cx="{x * r:.1f}" cy="{y * r:.1f}" r="{rr * r:.1f}"/>' for x, y, rr in parts)
        return f'<g {f}>{circles}</g>', -0.95 * r
    if shape == "triangle":
        pts = f"0,{-1.9 * r:.1f} {-1.05 * r:.1f},{-0.2 * r:.1f} {1.05 * r:.1f},{-0.2 * r:.1f}"
        return (f'<polygon points="{pts}" {f} stroke="{color}" stroke-width="{0.4 * r:.1f}" stroke-linejoin="round"/>'), -0.78 * r
    if shape == "drop":
        d = (f"M0 {-2.3 * r:.1f} C {0.3 * r:.1f} {-1.75 * r:.1f}, {0.95 * r:.1f} {-1.35 * r:.1f}, {0.95 * r:.1f} {-0.95 * r:.1f} "
             f"A {0.95 * r:.1f} {0.95 * r:.1f} 0 0 1 {-0.95 * r:.1f} {-0.95 * r:.1f} "
             f"C {-0.95 * r:.1f} {-1.35 * r:.1f}, {-0.3 * r:.1f} {-1.75 * r:.1f}, 0 {-2.3 * r:.1f} Z")
        return f'<path d="{d}" {f}/>', -0.95 * r
    return f'<ellipse cx="0" cy="{-0.9 * r:.1f}" rx="{1.15 * r:.1f}" ry="{0.9 * r:.1f}" {f}/>', -0.95 * r  # bean


def eyes(state: str, r: float, ey: float, phase: float) -> str:
    gap = 0.24 * r
    if state == "done":  # happy: two little arcs
        w = 0.13 * r
        return "".join(
            f'<path d="M{x - w:.1f} {ey + 0.05 * r:.1f} q{w:.1f} {-0.22 * r:.1f} {2 * w:.1f} 0" stroke="#fff" stroke-width="{0.09 * r:.1f}" '
            f'fill="none" stroke-linecap="round"/>' for x in (-gap, gap))
    if state == "quiet":  # asleep: two short lines
        w = 0.12 * r
        return "".join(
            f'<line x1="{x - w:.1f}" y1="{ey:.1f}" x2="{x + w:.1f}" y2="{ey:.1f}" stroke="#fff" stroke-width="{0.08 * r:.1f}" '
            f'stroke-linecap="round" opacity="0.9"/>' for x in (-gap, gap))
    big = state == "waiting"
    h = (0.5 if big else 0.4) * r
    w = (0.17 if big else 0.15) * r
    dx, dy = (0.07 * r, 0.06 * r) if state == "working" else (0.0, 0.0)
    blink = (f'<animate attributeName="height" values="{h:.1f};{h:.1f};{0.06 * r:.1f};{h:.1f}" keyTimes="0;0.92;0.96;1" '
             f'dur="{3.6 + phase:.2f}s" repeatCount="indefinite"/>'
             f'<animate attributeName="y" values="{ey - h / 2 + dy:.1f};{ey - h / 2 + dy:.1f};{ey - 0.03 * r + dy:.1f};{ey - h / 2 + dy:.1f}" '
             f'keyTimes="0;0.92;0.96;1" dur="{3.6 + phase:.2f}s" repeatCount="indefinite"/>')
    out = []
    for x in (-gap, gap):
        out.append(f'<rect x="{x - w / 2 + dx:.1f}" y="{ey - h / 2 + dy:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{w / 2:.1f}" fill="#fff" '
                   f'transform="rotate(-10 {x + dx:.1f} {ey + dy:.1f})">{blink}</rect>')
    return "".join(out)


def blob(a: dict, x: float, y: float, r: float, label: bool = True, link: str = "",
         look: tuple[str, str] | None = None, state_line: bool = True) -> str:
    """One session as a blob standing at (x, y)."""
    state = a["status"]
    color, shape = look or identity(a["id"])
    phase = _h(a["id"], "p") % 3000 / 1000
    shape_svg, ey = body(shape, r, color)
    top = -2.3 * r if shape == "drop" else -2.1 * r
    if state == "waiting":
        motion = (f'<animateTransform attributeName="transform" type="translate" values="0 0;0 {-0.28 * r:.1f};0 0;0 0" '
                  f'keyTimes="0;0.3;0.6;1" dur="1.3s" begin="-{phase:.2f}s" repeatCount="indefinite"/>')
    elif state == "working":
        motion = (f'<animateTransform attributeName="transform" type="scale" values="1 1;1.04 0.96;1 1" dur="0.9s" '
                  f'begin="-{phase:.2f}s" repeatCount="indefinite"/>')
    elif state == "done":
        motion = (f'<animateTransform attributeName="transform" type="rotate" values="-3;3;-3" dur="3.2s" '
                  f'begin="-{phase:.2f}s" repeatCount="indefinite"/>')
    else:
        motion = (f'<animateTransform attributeName="transform" type="scale" values="1 1;1.02 1.035;1 1" dur="4.5s" '
                  f'begin="-{phase:.2f}s" repeatCount="indefinite"/>')

    badge = ""
    bx, by = 0.95 * r, top + 0.15 * r
    if state == "waiting":
        badge = (f'<g transform="translate({bx:.1f} {by:.1f})"><circle r="{0.36 * r + 4:.1f}" fill="#ffd166" stroke="#2e2d2a" stroke-width="3"/>'
                 f'<text y="{0.16 * r + 2:.1f}" text-anchor="middle" font-size="{0.5 * r + 4:.1f}" font-weight="800" fill="#3d2a00" '
                 f'font-family="Tajawal, Geeza Pro, sans-serif">؟</text>'
                 f'<animateTransform attributeName="transform" type="translate" values="{bx:.1f} {by:.1f};{bx:.1f} {by - 5:.1f};{bx:.1f} {by:.1f}" '
                 f'dur="1.3s" repeatCount="indefinite"/></g>')
    elif state == "working":
        dots = "".join(
            f'<circle cx="{(i - 1) * 0.2 * r:.1f}" cy="0" r="{0.065 * r + 1:.1f}" fill="#1a6fe0">'
            f'<animate attributeName="cy" values="0;{-0.12 * r:.1f};0" dur="0.9s" begin="{i * 0.15:.2f}s" repeatCount="indefinite"/></circle>'
            for i in range(3))
        badge = (f'<g transform="translate({bx:.1f} {by:.1f})"><rect x="{-0.42 * r:.1f}" y="{-0.24 * r:.1f}" width="{0.84 * r:.1f}" '
                 f'height="{0.48 * r:.1f}" rx="{0.24 * r:.1f}" fill="#f5f5f4"/>{dots}</g>')
    elif state == "done":
        badge = (f'<g transform="translate({bx:.1f} {by:.1f})"><circle r="{0.3 * r + 3:.1f}" fill="#22c55e" stroke="#2e2d2a" stroke-width="3"/>'
                 f'<path d="M{-0.13 * r:.1f} 0 l{0.1 * r:.1f} {0.11 * r:.1f} l{0.18 * r:.1f} {-0.2 * r:.1f}" stroke="#fff" '
                 f'stroke-width="{0.07 * r + 1:.1f}" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>')
    else:
        badge = "".join(
            f'<text x="{bx + i * 8:.1f}" y="{by:.1f}" font-size="{0.36 * r + 4 - i * 3:.1f}" font-weight="800" fill="#a8a29e" '
            f'font-family="Montserrat, sans-serif" opacity="0">z'
            f'<animate attributeName="opacity" values="0;1;0" dur="3s" begin="{i * 1.5 - phase:.2f}s" repeatCount="indefinite"/>'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;6 -18" dur="3s" begin="{i * 1.5 - phase:.2f}s" '
            f'repeatCount="indefinite"/></text>' for i in range(2))

    title = escape(f"{a['title']}: {STATE_WORD[state]}")
    out = []
    if link:
        out.append(f'<a href="{escape(link)}" target="_top">')
    out.append(f'<g transform="translate({x:.1f} {y:.1f})"><title>{title}</title>')
    out.append(f'<ellipse cx="0" cy="2" rx="{0.95 * r:.1f}" ry="{0.13 * r + 2:.1f}" fill="#000" opacity="0.32"/>')
    out.append(f'<g>{motion}{shape_svg}{eyes(state, r, ey, phase)}</g>{badge}')
    if label:
        name = escape(_short(a["title"], 17 if state_line else 11))
        rtl = ' direction="rtl"' if any("؀" <= ch <= "ۿ" for ch in name[:4]) else ""
        out.append(f'<text y="{22:.1f}" text-anchor="middle" font-size="{14 if state_line else 12}" font-weight="700" fill="#f5f5f4" '
                   f'font-family="Montserrat, Tajawal, Geeza Pro, sans-serif"{rtl}>{name}</text>')
        if state_line:
            out.append(f'<text y="{39:.1f}" text-anchor="middle" font-size="12.5" font-weight="700" fill="{STATE_COLOR[state]}" '
                       f'font-family="Tajawal, Geeza Pro, sans-serif" direction="rtl">{STATE_WORD[state]}</text>')
    out.append("</g>")
    if link:
        out.append("</a>")
    return "".join(out)


def _short(title: str, limit: int = 17) -> str:
    import re
    t = title.strip() or title
    if len(t) <= limit:
        return t
    cut = t[:limit].rsplit(" ", 1)[0]
    if len(cut) < 9:
        cut = t[:limit]
    return cut.rstrip(" ,:-") + "…"


def icon(sid: str, state: str, size: int = 30, look: tuple[str, str] | None = None) -> str:
    """A small standalone blob for a list row, same colour and shape as in the room."""
    r = size * 0.36
    a = {"id": sid, "status": state, "title": ""}
    inner = blob(a, size / 2, size + 6, r, label=False, look=look)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size + 12} {size + 10}" width="{size + 12}" height="{size + 10}">'
            f'<g transform="translate(4 0)">{inner}</g></svg>')


def room(agents: list[dict], width: int = 960, links: bool = False) -> str:
    """All sessions piled on one smooth stage: waiting in front, working in the middle, the rest behind.
    Narrow rooms (the in-app pane) draw the resting ones smaller, without their state line, and at most 8."""
    compact = width < 600
    rest = sorted([a for a in agents if a["status"] in ("done", "quiet")], key=lambda a: a["ageS"])[:8 if compact else 12]
    groups = [
        (rest[::-1], 20 if compact else 26, 100 if compact else 128, False),
        ([a for a in agents if a["status"] == "working"], 30 if compact else 36, 136 if compact else 150, True),
        ([a for a in agents if a["status"] == "waiting"], 36 if compact else 44, 146 if compact else 150, True),
    ]
    rows = []
    for items, r, min_cell, full in groups:
        if not items:
            continue
        cell = max(2.9 * r, min_cell)
        per = max(1, int((width - 24) // cell))
        for i in range(0, len(items), per):
            rows.append((items[i:i + per], r, cell, full or not compact))
    placed = []
    y = 14.0
    for items, r, cell, full in rows:
        base = y + 2.8 * r
        n = len(items)
        x0 = width / 2 - cell * (n - 1) / 2
        for i, a in enumerate(items):
            jitter = ((_h(a["id"], "j") % 9) - 4) * 1.0
            placed.append((a, x0 + i * cell, base + jitter, r, full))
        y = base + (46 if full else 28)
    height = max(170, int(y + 10))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">',
             f'<defs><radialGradient id="stage" cx="50%" cy="40%" r="75%"><stop offset="0" stop-color="{STAGE_IN}"/>'
             f'<stop offset="1" stop-color="{STAGE_OUT}"/></radialGradient></defs>',
             f'<rect width="{width}" height="{height}" rx="22" fill="url(#stage)"/>']
    if not placed:
        parts.append(f'<text x="{width / 2}" y="{height / 2}" text-anchor="middle" font-size="18" fill="#a8a29e" '
                     f'font-family="Tajawal, Geeza Pro, sans-serif" direction="rtl">ما في احد شغال الحين</text>')
    looks = assign(agents)
    for a, x, by, r, full in placed:
        parts.append(blob(a, x, by, r, True, a.get("link", "") if links else "", looks.get(a["id"]), state_line=full))
    parts.append("</svg>")
    return "".join(parts)
