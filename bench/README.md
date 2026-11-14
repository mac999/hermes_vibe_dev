# Coding benchmark for a local Hermes agent

Nine small coding tasks with hidden tests. Each run copies a task's starter files into a
fresh git workdir, gives the agent only `TASK.md` as the prompt, then scores the result
against tests the agent never sees.

## Tasks

| id | kind | hidden tests |
|---|---|---|
| t1_ttl_cache | new data structure (TTL + LRU cache) | 13 |
| t2_ledger_bugfix | fix four reported bugs in existing code | 12 |
| t3_todo_cli | add features to a multi-file CLI package | 11 |
| t4_log_report | log parsing and aggregation | 9 |
| t5_notes_api | Flask REST API | 23 |
| t6_fefo_perf | make a slow function fast without changing results | 6 |
| t7_async_fetch | asyncio concurrency, retries, timeouts | 11 |
| t8_js_mdtable | JavaScript module (Node test runner) | 9 |
| t9_invoice_multicurrency | bug fix + multi-currency feature across a 7-module package | 25 |

Each task directory has `TASK.md` (the prompt), `starter/`, `hidden/` (scoring tests) and
`oracle/` (a reference solution that passes every hidden test).

## Requirements

- Hermes with a profile set up by `profile/apply-coder-profile.sh`
- A Python environment with `pytest` and `ruff`; Node.js 18+ for t8
- Optional: Claude Code (`claude`) to produce a reference run

## Run

```bash
export BENCH_PYTHON=/path/to/env/bin/python   # env with pytest + ruff, also put first on the agent's PATH
cd bench
./lane.sh my_run hermes qwen3.8-27b-64k coder          # all tasks, one configuration
./lane.sh my_run hermes qwen3.8-27b-64k coder t5_notes_api   # selected tasks
./lane.sh claude_ref claude                             # reference with Claude Code
python3 summary.py claude_ref my_run                    # comparison table
python3 speed.py qwen3.8-27b-64k qwen3.6-35b-a3b-64k    # prefill / decode speed
```

Results land in `results/<label>/` (`*.score.json`, the agent's stream log, stderr).
Workdirs are kept under `$BENCH_RUNS` (default `~/hbench_runs`) for inspection.
A lane holds a lock per label, so the same label cannot run twice at once.

## Validate the tasks

Before trusting scores on a new machine, check that every oracle passes and every starter fails:

```bash
for t in tasks/t*; do
  w=$(mktemp -d); cp -r $t/starter/. $w/; cp -r $t/oracle/. $w/
  $BENCH_PYTHON score.py $t $w --json | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['task'],d['hidden_passed'],'/',d['hidden_total'])"
done
```

## Reading the table

- `solved`: tasks where every hidden test passed
- `rate`: mean hidden-test pass rate over all tasks
- `tests`: runs in which the agent ran tests itself
- `*` after a score: the agent log mentions hidden-test paths (treat the score as invalid)

Run-to-run variance is real: repeat a configuration before drawing conclusions from one task.
