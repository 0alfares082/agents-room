"""Show mode keeps titles with stand-in names and drops every private word."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import board  # noqa: E402
import fixtures as fx  # noqa: E402
import room  # noqa: E402
import show  # noqa: E402

PRIVATE = ["Acme", "Globex", "خل الفيديو", "Continue with the two episodes", "deploy it",
           "عرفنا السبب", "اشغل اختبارات المشغل", "الحلقة الاولى", "نزل على الموقع", "research this"]


def snaps(tmp_path, monkeypatch):
    fx.scene(tmp_path)
    monkeypatch.setattr(board, "LEDGER_DIR", tmp_path / "no-ledgers")
    b = board.Board(tmp_path)
    b.app_dir = False
    real = b.snapshot()
    return real, show.redact(real)


def test_titles_keep_with_stand_in_names(tmp_path, monkeypatch):
    real, s = snaps(tmp_path, monkeypatch)
    titles = {a["status"]: a["title"] for a in s["agents"]}
    assert titles["working"] == "Nova Room play copies"
    assert titles["waiting"] == "Nova episode two"
    assert titles["done"] == "Atlas release"
    assert titles["quiet"] == "Old research"
    assert s["counts"] == real["counts"]
    assert [a["id"] for a in s["agents"]] == [a["id"] for a in real["agents"]]


def test_no_private_text_in_any_output(tmp_path, monkeypatch):
    _, s = snaps(tmp_path, monkeypatch)
    outputs = [json.dumps(s, ensure_ascii=False), room.room_svg(s, 960, "sm", True),
               json.dumps(room.pane_rows(s), ensure_ascii=False)]
    for out in outputs:
        for word in PRIVATE:
            assert word not in out, word
        assert "claude://" not in out
        assert not show.leaks().search(out), show.leaks().search(out)


def test_working_shows_generic_kind_and_waiting_a_plain_line(tmp_path, monkeypatch):
    _, s = snaps(tmp_path, monkeypatch)
    a = {x["status"]: x for x in s["agents"]}
    assert a["working"]["action"] == "يشغل امر"
    assert a["working"]["done"] == ["انجز 2 بنود"]
    assert a["waiting"]["waiting"] == ["ينطر قرارك"]
    assert a["done"]["latest"] == "" and a["done"]["action"] == ""


def test_titles_hidden_unless_config_allows(tmp_path, monkeypatch):
    import config
    monkeypatch.setitem(config.CONFIG, "showTitles", False)
    _, s = snaps(tmp_path, monkeypatch)
    titles = sorted(a["title"] for a in s["agents"])
    assert titles == ["Atlas · مهمة 1", "Nova · مهمة 1", "Nova · مهمة 2", "عام · مهمة 1"], titles


def test_alias_whole_words_and_fallback():
    assert show.alias("Acme lead") == "Nova lead"
    assert show.alias("one updated message to John (draft)") == "one updated message to Sam (draft)"
    assert show.alias("Johnson Monitor") == "Johnson Monitor"
    untitled = {"id": "x", "status": "quiet", "project": "Acme", "title": "reply to acme about the price",
                "titled": False, "ledger": None}
    out = show.redact({"agents": [untitled], "counts": {}})["agents"][0]
    assert out["title"] == "Nova · مهمة 1"
    assert out["project"] == "Nova" and out["tint"] == "#5cc8f5"
