import json
import subprocess
import sys
from pathlib import Path

from report import summarize

ROOT = Path(__file__).resolve().parent


def L(ip="1.1.1.1", ts="07/Nov/2026:10:00:00 +0000", req="GET / HTTP/1.1", status=200, size=10, lat=5):
    return f'{ip} - - [{ts}] "{req}" {status} {size} {lat}'


def test_empty():
    r = summarize([])
    assert r["total"] == 0 and r["malformed"] == 0
    assert r["latency_ms"] == {"p50": None, "p95": None, "max": None}
    assert r["status_classes"] == {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
    assert r["top_paths"] == [] and r["bytes_total"] == 0
    assert r["requests_per_hour_utc"] == {}


def test_malformed_counting():
    lines = [
        "",
        "garbage",
        L(status=600),
        L(status=99),
        L(lat=-3),
        L(lat="1.5"),
        L(ts="07/Foo/2026:10:00:00 +0000"),
        L(),
    ]
    r = summarize(lines)
    assert r["total"] == 1
    assert r["malformed"] == 7


def test_status_classes_and_1xx():
    lines = [L(status=s) for s in (200, 204, 301, 404, 404, 503, 101)]
    r = summarize(lines)
    assert r["status_classes"] == {"1xx": 1, "2xx": 2, "3xx": 1, "4xx": 2, "5xx": 1}


def test_top_paths_query_stripped_and_ties():
    reqs = ["GET /b?x=1 HTTP/1.1", "GET /b HTTP/1.1", "GET /a HTTP/1.1", "GET /a?z HTTP/1.1",
            "POST /c HTTP/1.1", "GET /d HTTP/1.1"]
    r = summarize([L(req=q) for q in reqs], top=3)
    assert r["top_paths"] == [["/a", 2], ["/b", 2], ["/c", 1]]


def test_percentiles_nearest_rank():
    lines = [L(lat=v) for v in [15, 20, 35, 40, 50]]
    r = summarize(lines)
    assert r["latency_ms"] == {"p50": 35, "p95": 50, "max": 50}
    lines = [L(lat=v) for v in range(1, 101)]
    r = summarize(lines)
    assert r["latency_ms"]["p50"] == 50 and r["latency_ms"]["p95"] == 95


def test_bytes_dash():
    r = summarize([L(size="-"), L(size=100)])
    assert r["bytes_total"] == 100


def test_hours_utc_conversion():
    lines = [
        L(ts="07/Nov/2026:23:59:58 +0900"),
        L(ts="07/Nov/2026:14:10:00 +0000"),
        L(ts="08/Nov/2026:00:30:00 +0100"),
        L(ts="07/Nov/2026:18:45:00 -0530"),
    ]
    r = summarize(lines)
    assert r["requests_per_hour_utc"] == {"2026-11-07T14": 1 + 1, "2026-11-07T23": 1, "2026-11-08T00": 1}


def test_cli(tmp_path):
    f = tmp_path / "x.log"
    f.write_text("\n".join([L(), L(req="GET /q HTTP/1.1"), "bad"]) + "\n")
    p = subprocess.run([sys.executable, str(ROOT / "report.py"), str(f), "--top", "1"],
                       capture_output=True, text=True)
    assert p.returncode == 0
    d = json.loads(p.stdout)
    assert d["total"] == 2 and d["malformed"] == 1
    assert d["top_paths"] == [["/", 1]]


def test_cli_missing_file(tmp_path):
    p = subprocess.run([sys.executable, str(ROOT / "report.py"), str(tmp_path / "nope.log")],
                       capture_output=True, text=True)
    assert p.returncode == 1
    assert p.stderr.strip()
