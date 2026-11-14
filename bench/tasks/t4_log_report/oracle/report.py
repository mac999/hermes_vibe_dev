import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone

LINE = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d{3}) (\d+|-) (\d+)$'
)


def _rank(sorted_vals, p):
    return sorted_vals[max(1, math.ceil(p / 100 * len(sorted_vals))) - 1]


def summarize(lines, top=5):
    total = malformed = bytes_total = 0
    classes = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
    paths = Counter()
    hours = Counter()
    lat = []
    for raw in lines:
        m = LINE.match(raw.rstrip("\r\n"))
        if not m:
            malformed += 1
            continue
        _, ts, _, target, _, status, size, latency = m.groups()
        status = int(status)
        try:
            when = datetime.strptime(ts, "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            malformed += 1
            continue
        if not 100 <= status <= 599:
            malformed += 1
            continue
        total += 1
        key = f"{status // 100}xx"
        classes[key] = classes.get(key, 0) + 1
        paths[target.split("?", 1)[0]] += 1
        bytes_total += 0 if size == "-" else int(size)
        lat.append(int(latency))
        hours[when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")] += 1
    lat.sort()
    latency_ms = (
        {"p50": _rank(lat, 50), "p95": _rank(lat, 95), "max": lat[-1]}
        if lat else {"p50": None, "p95": None, "max": None}
    )
    top_paths = sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    return {
        "total": total,
        "malformed": malformed,
        "status_classes": classes,
        "top_paths": [[p, n] for p, n in top_paths],
        "latency_ms": latency_ms,
        "bytes_total": bytes_total,
        "requests_per_hour_utc": dict(hours),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile")
    ap.add_argument("--top", type=int, default=5)
    a = ap.parse_args(argv)
    try:
        with open(a.logfile, encoding="utf-8") as f:
            result = summarize(f, a.top)
    except OSError as e:
        print(f"cannot read {a.logfile}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
