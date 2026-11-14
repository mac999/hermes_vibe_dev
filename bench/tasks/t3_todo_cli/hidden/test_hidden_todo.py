import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent


def run(tmp_path, *args, today="2026-05-10"):
    env = {
        "TODO_FILE": str(tmp_path / "todo.json"),
        "TODO_TODAY": today,
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(ROOT),
        "HOME": str(tmp_path),
    }
    return subprocess.run([sys.executable, "-m", "todo", *args], capture_output=True, text=True, env=env, cwd=ROOT)


def test_existing_behaviour_unchanged(tmp_path):
    assert run(tmp_path, "add", "buy milk").stdout.strip() == "added 1"
    run(tmp_path, "add", "write report")
    assert run(tmp_path, "done", "1").stdout.strip() == "done 1"
    assert run(tmp_path, "list").stdout.splitlines() == ["[x] 1: buy milk", "[ ] 2: write report"]
    assert run(tmp_path, "list", "--open").stdout.splitlines() == ["[ ] 2: write report"]
    r = run(tmp_path, "done", "99")
    assert r.returncode == 1


def test_add_with_due_and_list_suffix(tmp_path):
    assert run(tmp_path, "add", "pay rent", "--due", "2026-05-31").returncode == 0
    run(tmp_path, "add", "no due")
    assert run(tmp_path, "list").stdout.splitlines() == [
        "[ ] 1: pay rent (due 2026-05-31)",
        "[ ] 2: no due",
    ]


@pytest.mark.parametrize("bad", ["2026-02-30", "2026/05/01", "tomorrow", "2026-13-01"])
def test_invalid_due(tmp_path, bad):
    r = run(tmp_path, "add", "x", "--due", bad)
    assert r.returncode == 2
    assert "invalid due date" in r.stderr
    assert run(tmp_path, "list").stdout.strip() == ""


def test_overdue(tmp_path):
    run(tmp_path, "add", "past open", "--due", "2026-05-01")
    run(tmp_path, "add", "past done", "--due", "2026-05-02")
    run(tmp_path, "add", "today", "--due", "2026-05-10")
    run(tmp_path, "add", "future", "--due", "2026-06-01")
    run(tmp_path, "add", "none")
    run(tmp_path, "done", "2")
    out = run(tmp_path, "list", "--overdue").stdout.splitlines()
    assert out == ["[ ] 1: past open (due 2026-05-01)"]
    out = run(tmp_path, "list", "--overdue", today="2026-07-01").stdout.splitlines()
    assert out == [
        "[ ] 1: past open (due 2026-05-01)",
        "[ ] 3: today (due 2026-05-10)",
        "[ ] 4: future (due 2026-06-01)",
    ]


def seed(tmp_path):
    run(tmp_path, "add", 'say "hi", then leave', "--due", "2026-05-20")
    run(tmp_path, "add", "a | b")
    run(tmp_path, "add", "plain")
    run(tmp_path, "done", "2")


def test_export_csv_default_stdout(tmp_path):
    seed(tmp_path)
    r = run(tmp_path, "export")
    assert r.returncode == 0
    rows = list(csv.reader(io.StringIO(r.stdout)))
    assert rows[0] == ["id", "title", "done", "due"]
    assert rows[1:] == [
        ["1", 'say "hi", then leave', "false", "2026-05-20"],
        ["2", "a | b", "true", ""],
        ["3", "plain", "false", ""],
    ]


def test_export_status_filter(tmp_path):
    seed(tmp_path)
    rows = list(csv.reader(io.StringIO(run(tmp_path, "export", "--status", "open").stdout)))
    assert [r[0] for r in rows[1:]] == ["1", "3"]
    rows = list(csv.reader(io.StringIO(run(tmp_path, "export", "--status", "done").stdout)))
    assert [r[0] for r in rows[1:]] == ["2"]


def test_export_md_to_file(tmp_path):
    seed(tmp_path)
    out = tmp_path / "out.md"
    r = run(tmp_path, "export", "--format", "md", "--out", str(out))
    assert r.returncode == 0
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].replace(" ", "") == "|id|title|done|due|"
    assert lines[1].replace(" ", "") == "|---|---|---|---|"
    cells = [[c.strip() for c in ln.strip().strip("|").split(" | ")] for ln in lines[2:]]
    assert len(lines) == 5
    assert "a \\| b" in lines[3]
    assert cells[0][0] == "1" and cells[0][3] == "2026-05-20"
    assert lines[3].replace(" ", "").endswith("|x||")


def test_old_json_format_still_loads(tmp_path):
    (tmp_path / "todo.json").write_text(json.dumps([{"id": 1, "title": "legacy", "done": False}]))
    assert run(tmp_path, "list").stdout.splitlines() == ["[ ] 1: legacy"]
    run(tmp_path, "add", "new", "--due", "2026-05-11")
    data = json.loads((tmp_path / "todo.json").read_text())
    assert data[0]["title"] == "legacy" and data[1]["title"] == "new"
