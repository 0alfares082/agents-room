import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import board  # noqa: E402
import fixtures as fx  # noqa: E402


def snap(folder, ledger_dir=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(board, "LEDGER_DIR", ledger_dir or folder / "no-ledgers")
    b = board.Board(folder)
    b.app_dir = False  # never read the real desktop app's sessions in tests
    return b, b.snapshot()


def by_title(s):
    return {a["title"]: a for a in s["agents"]}


def test_each_status_and_headless_hidden(tmp_path, monkeypatch):
    fx.scene(tmp_path)
    _, s = snap(tmp_path, monkeypatch=monkeypatch)
    a = by_title(s)
    assert a["Acme Room play copies"]["status"] == "working"
    assert a["Acme episode two"]["status"] == "waiting"
    assert a["Globex release"]["status"] == "done"
    assert a["Old research"]["status"] == "quiet"
    assert len(s["agents"]) == 4, "the sdk-py headless run must not show"
    assert s["counts"] == {"waiting": 1, "working": 1, "done": 1, "quiet": 1}
    assert [x["status"] for x in s["agents"]] == ["waiting", "working", "done", "quiet"]


def test_working_card_fields(tmp_path, monkeypatch):
    fx.scene(tmp_path)
    _, s = snap(tmp_path, monkeypatch=monkeypatch)
    w = by_title(s)["Acme Room play copies"]
    assert w["action"] == "اشغل اختبارات المشغل"
    assert w["done"] == ["عرفنا السبب", "قسنا الحجم"]
    assert w["ask"] == "خل الفيديو يشتغل داخل الغرفة"
    assert w["project"] == "Acme"


def test_waiting_items_and_no_hamza_or_dash(tmp_path, monkeypatch):
    fx.scene(tmp_path)
    _, s = snap(tmp_path, monkeypatch=monkeypatch)
    q = by_title(s)["Acme episode two"]
    assert any("A:" in item for item in q["waiting"])
    d = by_title(s)["Globex release"]
    assert "—" not in d["latest"] and "،" in d["latest"]
    blob = json.dumps(s, ensure_ascii=False)
    assert not any(ch in blob for ch in "أإآ")


def test_answer_after_question_is_not_waiting(tmp_path, monkeypatch):
    ids = fx.scene(tmp_path)
    fx.write(tmp_path, ids["waiting"], [fx.human("A", 5), fx.say("تمام، بنطر القواعد.", 2)])
    _, s = snap(tmp_path, monkeypatch=monkeypatch)
    assert by_title(s)["Acme episode two"]["status"] == "done"


def test_incremental_read_picks_up_new_action(tmp_path, monkeypatch):
    ids = fx.scene(tmp_path)
    b, s = snap(tmp_path, monkeypatch=monkeypatch)
    assert by_title(s)["Acme Room play copies"]["action"] == "اشغل اختبارات المشغل"
    fx.write(tmp_path, ids["working"], [fx.tool_result(2), fx.tool("انشر على السيرفر", 1)])
    s2 = b.snapshot()
    w = by_title(s2)["Acme Room play copies"]
    assert w["action"] == "انشر على السيرفر"
    assert w["recent"][0] == "اشغل اختبارات المشغل"


def test_half_written_last_line_is_kept_for_later(tmp_path, monkeypatch):
    ids = fx.scene(tmp_path)
    b, _ = snap(tmp_path, monkeypatch=monkeypatch)
    row = json.dumps(fx.tool("خطوة جديدة", 1), ensure_ascii=False)
    path = tmp_path / f"{ids['working']}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(row[:40])
    assert by_title(b.snapshot())["Acme Room play copies"]["action"] == "اشغل اختبارات المشغل"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(row[40:] + "\n")
    assert by_title(b.snapshot())["Acme Room play copies"]["action"] == "خطوة جديدة"


def test_same_title_after_clear_shows_once(tmp_path, monkeypatch):
    fx.write(tmp_path, "11111111-old", [fx.title("acme", "x"), fx.human("old", 7000), fx.say("قديم", 6900)])
    fx.write(tmp_path, "22222222-new", [fx.title("acme", "y"), fx.human("new", 60), fx.say("يديد", 30)])
    _, s = snap(tmp_path, monkeypatch=monkeypatch)
    rows = [a for a in s["agents"] if a["title"] == "acme"]
    assert len(rows) == 1 and rows[0]["latest"] == "يديد"


def test_ledger_is_attached_by_session_prefix(tmp_path, monkeypatch):
    ids = fx.scene(tmp_path / "p")
    led_dir = tmp_path / "ledgers" / "2026-10-16-x"
    led_dir.mkdir(parents=True)
    (led_dir / "ledger.json").write_text(json.dumps({
        "id": "2026-10-16-x", "goal": "Play copies live", "status": "active", "updated": "2026-10-16T15:00:00+00:00",
        "checks": {"a": {"last": {"ok": True}}, "b": {"last": {"ok": False}}, "c": {}},
        "sessions": [{"id": ids["working"]}],
    }))
    _, s = snap(tmp_path / "p", ledger_dir=tmp_path / "ledgers", monkeypatch=monkeypatch)
    led = by_title(s)["Acme Room play copies"]["ledger"]
    assert led["passed"] == 1 and led["failed"] == 1 and led["total"] == 3


def test_cross_session_and_hook_messages_are_not_his_words(tmp_path, monkeypatch):
    sid = "33333333-0000"
    fx.write(tmp_path, sid, [
        fx.title("relay", sid),
        fx.human("ابي التقرير", 600),
        fx.human("Another Claude session sent a message: hi", 300),
        fx.human("Stop hook feedback: check", 200),
        fx.say("تمام", 100),
    ])
    _, s = snap(tmp_path, monkeypatch=monkeypatch)
    assert by_title(s)["relay"]["ask"] == "ابي التقرير"


def test_clean_and_bullets():
    assert board.clean("**أهلا** — إلى آخره") == "اهلا، الى اخره"
    text = "**اللي انسوى**\n- واحد\n- اثنين\n\n**الباقي عليك**\n1. قرار"
    assert board.bullets_under(text, board.DONE_HEAD) == ["واحد", "اثنين"]
    assert board.bullets_under(text, board.WAIT_HEAD) == ["قرار"]


def test_app_summary_and_link_and_worktree_session(tmp_path, monkeypatch):
    projects = tmp_path / "projects" / "-home-x-myproject"
    ids = fx.scene(projects)
    wt = tmp_path / "projects" / "-home-x-myproject-worlds-wt"
    fx.write(wt, "ffffffff-wt", [fx.title("Fix 403 label", "w"), fx.human("fix it", 100), fx.tool("يصلح الرسالة", 3)])
    app = tmp_path / "app" / "org" / "acct"
    app.mkdir(parents=True)
    def rec(local, cli, cwd, **extra):
        (app / f"{local}.json").write_text(json.dumps({"sessionId": local, "cliSessionId": cli, "cwd": cwd, **extra}))
    rec("local_wt", "ffffffff-wt", "/home/x/myproject/worlds/wt", title="Fix 403 label")
    rec("local_old", ids["quiet"], "/home/x/myproject", isArchived=True)
    monkeypatch.setattr(board, "LEDGER_DIR", tmp_path / "none")
    b = board.Board(projects)
    b.app_dir = tmp_path / "app"
    s = by_title(b.snapshot())
    assert s["Fix 403 label"]["status"] == "working"
    assert s["Fix 403 label"]["link"] == "claude://claude.ai/epitaxy/local_wt"
    assert "Old research" not in s, "an archived session stays hidden"
