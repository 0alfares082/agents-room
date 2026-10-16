#!/usr/bin/env python3
"""Local server for the agents board. Stdlib only, binds 127.0.0.1 (transcripts are private).

    python3 board/serve.py [--port 8795] [--host 127.0.0.1]

    GET /api/board   snapshot JSON (board.py), rebuilt at most once a second
    ?show=1          on any page or API: show mode (show.py), stand-in names and no private text
    GET /<path>      static files from board/ only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))

import board as boardlib  # noqa: E402
import room as roomlib  # noqa: E402
import show as showlib  # noqa: E402

DEFAULT_PORT = 8795
STATIC = {"index.html", "styles.css", "app.js", "favicon.svg"}
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
        ".json": "application/json; charset=utf-8"}


class Cache:
    def __init__(self) -> None:
        self.board = boardlib.Board()
        self.lock = threading.Lock()
        self.at = 0.0
        self.body = b"{}"
        self.show_body = b"{}"
        self.snap: dict = {}
        self.show_snap: dict = {}
        self.svgs: dict[tuple, tuple[str, str]] = {}

    def use(self, projects_dir: Path) -> None:
        self.board = boardlib.Board(projects_dir)

    def refresh(self) -> None:
        if time.time() - self.at >= 1.0:
            self.snap = self.board.snapshot()
            self.body = json.dumps(self.snap, ensure_ascii=False).encode("utf-8")
            self.show_snap = showlib.redact(self.snap)
            self.show_body = json.dumps(self.show_snap, ensure_ascii=False).encode("utf-8")
            self.svgs = {}
            self.at = time.time()

    def svg_for(self, width: int, size: str = "sm", links: bool = False, show: bool = False) -> tuple[str, str]:
        key = (width, size, links, show)
        if key not in self.svgs:
            svg = roomlib.room_svg(self.show_snap if show else self.snap, width, size, links)
            self.svgs[key] = (svg, roomlib.svg_signature(svg))
        return self.svgs[key]

    def get(self, show: bool = False) -> bytes:
        with self.lock:
            self.refresh()
            return self.show_body if show else self.body

    def room(self, width: int, size: str = "sm", links: bool = False, show: bool = False) -> tuple[str, str]:
        with self.lock:
            self.refresh()
            return self.svg_for(width, size, links, show)

    def pane(self, width: int, show: bool = False) -> bytes:
        with self.lock:
            self.refresh()
            snap = self.show_snap if show else self.snap
            svg, sig = self.svg_for(width, show=show)
            m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
            data = {"generatedAt": snap.get("generatedAt"), "counts": snap.get("counts"),
                    "svg": svg, "svgSig": sig, "svgW": int(m.group(1)) if m else width,
                    "svgH": int(m.group(2)) if m else 300, "agents": roomlib.pane_rows(snap)}
            return json.dumps(data, ensure_ascii=False).encode("utf-8")


CACHE = Cache()


class Handler(BaseHTTPRequestHandler):
    server_version = "agents-board"

    def log_message(self, fmt, *args):  # quiet
        pass

    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if getattr(self, "sig_header", ""):
            self.send_header("X-Room-Sig", self.sig_header)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self.sig_header = ""
        parts = urlsplit(self.path)
        path = unquote(parts.path)
        width, size, links, show = roomlib.W, "sm", False, False
        for kv in parts.query.split("&"):
            if kv.startswith("w=") and kv[2:].isdigit():
                width = max(360, min(2400, int(kv[2:])))
            elif kv == "size=hd":
                size = "hd"
            elif kv == "links=1":
                links = True
            elif kv == "show=1":
                show = True
        if path == "/api/board":
            try:
                return self.send(200, CACHE.get(show), MIME[".json"])
            except Exception as exc:  # report, never crash the server
                body = json.dumps({"error": str(exc)[:300]}).encode()
                return self.send(500, body, MIME[".json"])
        if path in ("/api/room.svg", "/api/pane"):
            try:
                if path == "/api/pane":
                    return self.send(200, CACHE.pane(width, show), MIME[".json"])
                svg, sig = CACHE.room(width, size, links, show)
                self.sig_header = sig
                return self.send(200, svg.encode("utf-8"), MIME[".svg"])
            except Exception as exc:
                return self.send(500, json.dumps({"error": str(exc)[:300]}).encode(), MIME[".json"])
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        sprite = re.fullmatch(r"sprites/hd/([a-z]+-[a-z]+)\.webp", name)
        if sprite:
            file = HERE / "sprites" / "hd" / f"{sprite.group(1)}.webp"
            if file.is_file():
                return self.send(200, file.read_bytes(), "image/webp")
            return self.send(404, b"not found", "text/plain; charset=utf-8")
        if name not in STATIC:
            return self.send(404, b"not found", "text/plain; charset=utf-8")
        file = HERE / name
        if not file.is_file():
            return self.send(404, b"not found", "text/plain; charset=utf-8")
        self.send(200, file.read_bytes(), MIME.get(file.suffix, "application/octet-stream"))

    do_HEAD = do_GET


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--projects-dir", type=Path, help="transcripts folder (tests use a fixture)")
    ap.add_argument("--ledger-dir", type=Path, help="task ledger folder (tests use a fixture)")
    args = ap.parse_args()
    if args.ledger_dir:
        boardlib.LEDGER_DIR = args.ledger_dir
    if args.projects_dir:
        CACHE.use(args.projects_dir)
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("refusing a non-local host: transcripts are private", file=sys.stderr)
        return 2
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.daemon_threads = True
    print(f"agents board on http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
