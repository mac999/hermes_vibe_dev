#!/usr/bin/env bash
# Run all tasks for one configuration.
# usage: lane.sh <label> <hermes|claude> [model] [profile] [task ...]
set -u
LABEL=$1 AGENT=$2 MODEL=${3:-} PROFILE=${4:-coder}
shift $(( $# < 4 ? $# : 4 ))
TASKS=${*:-t1_ttl_cache t2_ledger_bugfix t3_todo_cli t4_log_report t5_notes_api t6_fefo_perf t7_async_fetch t8_js_mdtable t9_invoice_multicurrency}
cd "$(dirname "$0")"
mkdir -p results
exec 9>"results/.lock-$LABEL"
flock -n 9 || { echo "lane $LABEL is already running" >&2; exit 1; }
for t in $TASKS; do ./run.sh "$AGENT" "$LABEL" "$t" "$MODEL" "$PROFILE" | tail -1; done
python3 summary.py "$LABEL"
