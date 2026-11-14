#!/usr/bin/env python3
"""Measure prefill and decode speed of Ollama models with a fixed prompt.

usage: speed.py <model> [model ...]
Spark estimates scale decode by memory bandwidth (273 / 1792 GB/s) and prefill by
dense BF16 compute (about 0.45x); they are rough planning numbers, not measurements.
"""
import json
import os
import sys
import urllib.request

URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434") + "/api/generate"
DECODE_RATIO = 273 / 1792
PREFILL_RATIO = 0.45


def prompt(n_lines=420):
    # ~8K tokens of varied but deterministic code-like text
    rows = [f"def f{i}(x):\n    return (x * {i % 97} + {i * 7 % 13}) % {i % 11 + 2}\n" for i in range(n_lines)]
    return "".join(rows) + "\nExplain in about 200 words what these functions have in common."


def run(model, text=None):
    body = {"model": model, "prompt": text or prompt(), "stream": False, "think": False,
            "options": {"num_predict": 256, "temperature": 0}}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.load(r)
    pp = d["prompt_eval_count"] / (d["prompt_eval_duration"] / 1e9)
    tg = d["eval_count"] / (d["eval_duration"] / 1e9)
    return d["prompt_eval_count"], pp, tg


if __name__ == "__main__":
    print(f"{'model':40}{'prompt':>8}{'pp tok/s':>10}{'tg tok/s':>10}{'spark pp':>10}{'spark tg':>10}")
    for m in sys.argv[1:]:
        run(m, "Say hi.")  # warm-up with a different prompt so the timed prefill is uncached
        n, pp, tg = run(m)
        print(f"{m:40}{n:>8}{pp:>10.0f}{tg:>10.1f}{pp * PREFILL_RATIO:>10.0f}{tg * DECODE_RATIO:>10.1f}")
