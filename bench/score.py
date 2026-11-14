#!/usr/bin/env python3
"""Score one finished workdir against a task's hidden tests.

usage: score.py <task_dir> <workdir> [--json]
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Interpreter that has pytest and ruff (the same environment the agent uses).
PY = os.environ.get("BENCH_PYTHON", sys.executable)
RUFF = os.environ.get("BENCH_RUFF") or str(Path(PY).with_name("ruff"))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_pytest(cwd, target):
    p = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", *target.split()],
                       cwd=cwd, capture_output=True, text=True, timeout=600)
    # the summary line ("3 failed, 10 passed in 0.5s"); plugins may print warnings after it
    lines = [ln for ln in (p.stdout + p.stderr).splitlines()
             if re.search(r"\d+ (?:passed|failed|errors?)\b.* in [\d.]+s", ln)]
    tail = lines[-1:] or [""]
    passed = sum(int(n) for n in re.findall(r"(\d+) passed", tail[0]))
    failed = sum(int(n) for n in re.findall(r"(\d+) (?:failed|errors?)\b", tail[0]))
    return passed, failed, (p.stdout + p.stderr)[-3000:]


def run_node(cwd, target):
    p = subprocess.run(["node", "--test", "--test-reporter=tap", *target.split()],
                       cwd=cwd, capture_output=True, text=True, timeout=300)
    out = p.stdout
    passed = int((re.search(r"^# pass (\d+)", out, re.M) or [0, 0])[1])
    failed = int((re.search(r"^# fail (\d+)", out, re.M) or [0, 0])[1])
    if passed + failed == 0:
        failed = 1
    return passed, failed, (out + p.stderr)[-3000:]


def score(task_dir, workdir):
    task_dir, workdir = Path(task_dir), Path(workdir)
    res = {"task": task_dir.name}
    with tempfile.TemporaryDirectory(prefix="hbench_score_") as tmp:
        tmp = Path(tmp) / "w"
        shutil.copytree(workdir, tmp, ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"))
        hidden = sorted(p for p in (task_dir / "hidden").iterdir() if p.is_file())
        for h in hidden:
            shutil.copy(h, tmp / h.name)
        passed = failed = 0
        logs = []
        for h in hidden:
            fn = run_node if h.suffix == ".js" else run_pytest
            p, f, log = fn(tmp, h.name)
            passed, failed = passed + p, failed + f
            logs.append(log)
        total = passed + failed
        res["hidden_passed"], res["hidden_total"] = passed, total
        res["hidden_rate"] = round(passed / total, 4) if total else 0.0
        res["hidden_log_tail"] = "\n".join(logs)[-2000:]

        # visible tests shipped with the starter must be untouched and still pass
        vis = [p for p in (task_dir / "starter").rglob("test_*.py")]
        res["visible_untouched"] = all((workdir / v.relative_to(task_dir / "starter")).exists()
                                       and sha(workdir / v.relative_to(task_dir / "starter")) == sha(v)
                                       for v in vis)
        if vis:
            vp, vf, _ = run_pytest(tmp, " ".join(str(v.relative_to(task_dir / "starter")) for v in vis))
            res["visible_pass"] = vf == 0 and vp > 0
        else:
            res["visible_pass"] = None

        # agent-written tests: count and whether they pass
        own = [p for p in tmp.rglob("*") if p.is_file() and p.name not in {h.name for h in hidden}
               and (re.match(r"test_.*\.py$", p.name) or p.name.endswith(".test.js"))
               and not any(p.name == v.name for v in vis)]
        res["own_test_files"] = len(own)
        if own:
            if own[0].suffix == ".js":
                op, of, _ = run_node(tmp, " ".join(str(p.relative_to(tmp)) for p in own))
            else:
                op, of, _ = run_pytest(tmp, " ".join(str(p.relative_to(tmp)) for p in own))
            res["own_tests_passed"], res["own_tests_failed"] = op, of

        pyfiles = [str(p.relative_to(tmp)) for p in tmp.rglob("*.py") if p.name not in {h.name for h in hidden}]
        if pyfiles:
            r = subprocess.run([RUFF, "check", "--quiet", "--select", "E,F", "--ignore", "E501,E741",
                                "--output-format", "concise", *pyfiles], cwd=tmp, capture_output=True, text=True)
            res["lint_issues"] = len([ln for ln in r.stdout.splitlines() if re.match(r"\S+:\d+:\d+:", ln)])
        else:
            res["lint_issues"] = 0
    return res


if __name__ == "__main__":
    r = score(sys.argv[1], sys.argv[2])
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False))
    else:
        log = r.pop("hidden_log_tail")
        print(json.dumps(r, ensure_ascii=False, indent=1))
        if r["hidden_rate"] < 1:
            print(log[-1500:])
