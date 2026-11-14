#!/usr/bin/env python3
"""Aggregate results/<label>/*.score.json into one comparison table.

usage: summary.py [label ...]   (default: every label under results/)
"""
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
# hidden-test counts the oracle solutions pass; used as fixed denominators
TOTALS = {"t1_ttl_cache": 13, "t2_ledger_bugfix": 12, "t3_todo_cli": 11, "t4_log_report": 9,
          "t5_notes_api": 23, "t6_fefo_perf": 6, "t7_async_fetch": 11, "t8_js_mdtable": 9,
          "t9_invoice_multicurrency": 25}


def load(label):
    rows = {}
    for f in sorted((BENCH / "results" / label).glob("*.score.json")):
        try:
            d = json.loads(f.read_text())
        except ValueError:
            continue  # still being written
        rows[d["task"]] = d
    return rows


def main(labels):
    labels = labels or sorted(p.name for p in (BENCH / "results").iterdir()
                              if p.is_dir() and p.name != "smoke")
    head = f"{'label':26}" + "".join(f"{t[:2]:>7}" for t in TOTALS) + \
        f"{'solved':>8}{'rate':>7}{'lint':>6}{'tests':>7}{'min':>7}"
    print(head)
    print("-" * len(head))
    for label in labels:
        rows = load(label)
        cells, solved, rates, lint, tested, secs = [], 0, [], 0, 0, 0
        for t, n in TOTALS.items():
            d = rows.get(t)
            if not d:
                cells.append(f"{'-':>7}")
                continue
            p = min(d["hidden_passed"], n)
            rates.append(p / n)
            solved += p == n
            lint += d.get("lint_issues", 0)
            tested += bool(d.get("ran_tests"))
            secs += d.get("seconds", 0)
            mark = "*" if d.get("peeked_hidden") else ""
            cells.append(f"{p:>4}/{n:<2}{mark}"[:7].rjust(7))
        rate = sum(rates) / len(TOTALS)
        print(f"{label:26}" + "".join(cells) +
              f"{solved:>5}/{len(TOTALS)}{rate:>7.0%}{lint:>6}{tested:>5}/{len(rows)}{secs / 60:>7.1f}")
    print("\nsolved = tasks with every hidden test passing; rate = mean hidden pass rate over all tasks;")
    print("tests = runs where the agent executed tests itself; * = agent log references hidden-test paths")


if __name__ == "__main__":
    main(sys.argv[1:])
