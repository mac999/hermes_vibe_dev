#!/usr/bin/env python3
"""Measure prefill and decode speed through an OpenAI-compatible endpoint.

usage: speed_openai.py <base_url> <model> [model ...]
Two prompts: 'explain' (same text as speed.py) and 'code' (code generation, where
speculative decoding usually accepts more draft tokens). Thinking is disabled.
"""
import json
import sys
import time
import urllib.request

from speed import prompt

CODE = ("Write a complete Python module implementing an LRU cache class with get, put, "
        "delete, resize and stats methods, type hints and docstrings, followed by 12 pytest tests.")


def run(base, model, text, max_tokens):
    body = {"model": model, "messages": [{"role": "user", "content": text}], "stream": True,
            "max_tokens": max_tokens, "temperature": 0, "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False}, "reasoning_effort": "none"}
    req = urllib.request.Request(base + "/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t0 = time.time(); first = None; usage = None
    with urllib.request.urlopen(req, timeout=1800) as r:
        for line in r:
            line = line.strip()
            if not line.startswith(b"data:") or line.endswith(b"[DONE]"):
                continue
            d = json.loads(line[5:])
            if d.get("usage"):
                usage = d["usage"]
            ch = d.get("choices") or []
            if first is None and ch and (ch[0]["delta"].get("content") or ch[0]["delta"].get("reasoning_content")):
                first = time.time()
    t1 = time.time()
    n_in, n_out = usage["prompt_tokens"], usage["completion_tokens"]
    return n_in, n_in / (first - t0), (n_out - 1) / (t1 - first), n_out


if __name__ == "__main__":
    base = sys.argv[1].rstrip("/")
    print(f"{'model':28}{'test':>8}{'prompt':>8}{'pp tok/s':>10}{'out':>6}{'tg tok/s':>10}")
    for m in sys.argv[2:]:
        run(base, m, "Say hi.", 8)
        for name, text, mt in (("explain", prompt(), 256), ("code", CODE, 1200)):
            n, pp, tg, out = run(base, m, text, mt)
            print(f"{m:28}{name:>8}{n:>8}{pp:>10.0f}{out:>6}{tg:>10.1f}")
