#!/usr/bin/env bash
# Run one agent on one task in a fresh workdir, then score it.
# usage: run.sh <hermes|claude> <label> <task_id> [model] [profile]
set -u
AGENT=$1 LABEL=$2 TASK=$3 MODEL=${4:-} PROFILE=${5:-coder}
BENCH=$(cd "$(dirname "$0")" && pwd)
TDIR=$BENCH/tasks/$TASK
RUN=${BENCH_RUNS:-$HOME/hbench_runs}/$LABEL/$TASK
OUT=$BENCH/results/$LABEL
BUDGET=${BUDGET:-1500}
mkdir -p "$OUT"
rm -rf "$RUN" && mkdir -p "$RUN"
cp -r "$TDIR/starter/." "$RUN/"
( cd "$RUN" && git init -q && git add -A && \
  git -c user.name=bench -c user.email=bench@localhost commit -q -m starter --allow-empty )

# Put the agent's Python environment first when BENCH_PYTHON points at it.
[ -n "${BENCH_PYTHON:-}" ] && export PATH="$(dirname "$BENCH_PYTHON"):$PATH"
T0=$(date +%s)
cd "$RUN"
case $AGENT in
  hermes)
    timeout "$BUDGET" hermes -p "$PROFILE" chat --query-file "$TDIR/TASK.md" --oneshot \
      ${MODEL:+-m "$MODEL"} --max-turns 150 --format stream-json \
      > "$OUT/$TASK.log.jsonl" 2> "$OUT/$TASK.err.log"
    ;;
  claude)
    timeout "$BUDGET" claude -p "$(cat "$TDIR/TASK.md")" ${MODEL:+--model "$MODEL"} \
      --output-format stream-json --verbose --permission-mode acceptEdits \
      --allowedTools "Read" "Write" "Edit" "Glob" "Grep" \
        "Bash(python:*)" "Bash(python3:*)" "Bash(pytest:*)" "Bash(node:*)" \
        "Bash(ls:*)" "Bash(cat:*)" "Bash(head:*)" "Bash(wc:*)" "Bash(git status:*)" "Bash(git diff:*)" \
      > "$OUT/$TASK.log.jsonl" 2> "$OUT/$TASK.err.log" < /dev/null
    ;;
  *) echo "unknown agent $AGENT" >&2; exit 2 ;;
esac
RC=$?
SECS=$(( $(date +%s) - T0 ))
cd "$BENCH"
"${BENCH_PYTHON:-python3}" score.py "$TDIR" "$RUN" --json > "$OUT/$TASK.score.json"
python3 - "$OUT" "$TASK" "$AGENT" "${MODEL:-default}" "$RC" "$SECS" "$RUN" <<'PY'
import json, re, sys
out, task, agent, model, rc, secs, run = sys.argv[1:]
log = open(f"{out}/{task}.log.jsonl", encoding="utf-8", errors="replace").read()
s = json.load(open(f"{out}/{task}.score.json"))
tool_calls = len(re.findall(r'"type":\s*"tool_use"|"tool_call"|"event":\s*"tool\.started"|"tool\.call', log))
ran_tests = bool(re.search(r"pytest|node --test|unittest", log))
peeked = bool(re.search(r"/bench/tasks/|hidden/test_hidden|hidden_mdtable", log))
s.update(agent=agent, model=model, exit_code=int(rc), seconds=int(secs), tool_calls=tool_calls,
         ran_tests=ran_tests, peeked_hidden=peeked, workdir=run)
json.dump(s, open(f"{out}/{task}.score.json", "w"), ensure_ascii=False, indent=1)
print(f"{task:18} {agent:6} {model:28} hidden {s['hidden_passed']}/{s['hidden_total']}  "
      f"own_tests={s.get('own_test_files')} lint={s['lint_issues']} {secs}s rc={rc} tests_run={ran_tests}")
PY
