import subprocess
import sys


def run(tmp_path, *args):
    env = {"TODO_FILE": str(tmp_path / "todo.json"), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, "-m", "todo", *args], capture_output=True, text=True, env=env)


def test_add_list_done(tmp_path):
    assert run(tmp_path, "add", "buy milk").stdout.strip() == "added 1"
    run(tmp_path, "add", "write report")
    run(tmp_path, "done", "1")
    out = run(tmp_path, "list").stdout.splitlines()
    assert out == ["[x] 1: buy milk", "[ ] 2: write report"]
