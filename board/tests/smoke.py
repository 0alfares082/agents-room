#!/usr/bin/env python3
"""Smoke test: start the real server on a free port against a made-up projects folder and
check every endpoint answers. Touches nothing outside a temporary folder.

    python3 board/tests/smoke.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as fx  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    try:
        fx.scene(tmp / "projects" / "-home-x-demo")
        cfg = tmp / "config.json"
        cfg.write_text(json.dumps({"projects": [{"name": "Acme", "keywords": ["acme"], "showAs": "Nova"}],
                                   "showTitles": True}))
        port = free_port()
        env = dict(os.environ, AGENTS_ROOM_CONFIG=str(cfg), PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.Popen([sys.executable, str(HERE.parent / "serve.py"), "--port", str(port),
                                 "--projects-dir", str(tmp / "projects"), "--ledger-dir", str(tmp / "none")],
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen(base + "/api/board", timeout=2)
                    break
                except OSError:
                    time.sleep(0.1)
            get = lambda p: urllib.request.urlopen(base + p, timeout=10).read().decode()  # noqa: E731
            board = json.loads(get("/api/board"))
            titles = sorted(a["title"] for a in board["agents"])
            assert titles == ["Acme Room play copies", "Acme episode two", "Globex release", "Old research"], titles
            shown = json.loads(get("/api/board?show=1"))
            assert "Acme" not in json.dumps(shown) and "Nova Room play copies" in json.dumps(shown)
            assert get("/api/room.svg?w=960&links=1").startswith("<svg")
            pane = json.loads(get("/api/pane?w=440&show=1"))
            assert pane["svg"].startswith("<svg") and len(pane["agents"]) == 4
            assert "غرفة الوكلاء" in get("/")
        finally:
            proc.terminate()
            proc.wait(5)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # Windows can hold a file a moment after the server stops
    print(f"PASS smoke: 4 sessions served on port {port}, show mode swaps the names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
