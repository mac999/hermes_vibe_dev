import asyncio

import pytest

from fetcher import Result, TransientError, fetch_all


def run(coro):
    return asyncio.run(coro)


class Recorder:
    def __init__(self):
        self.sleeps = []

    async def __call__(self, s):
        self.sleeps.append(s)


def test_basic_ok_and_order():
    async def fetch(url):
        await asyncio.sleep(0.01 if url == "a" else 0)
        return url.encode()

    out = run(fetch_all(["a", "b", "c"], fetch))
    assert list(out) == ["a", "b", "c"]
    assert out["a"] == Result(True, b"a", None, 1)


def test_concurrency_limit_respected():
    state = {"cur": 0, "max": 0}

    async def fetch(url):
        state["cur"] += 1
        state["max"] = max(state["max"], state["cur"])
        await asyncio.sleep(0.01)
        state["cur"] -= 1
        return b"x"

    run(fetch_all([str(i) for i in range(30)], fetch, concurrency=4))
    assert state["max"] == 4


def test_invalid_concurrency():
    async def fetch(url):
        return b""

    with pytest.raises(ValueError):
        run(fetch_all(["a"], fetch, concurrency=0))


def test_retry_then_success_with_backoff():
    calls = {"n": 0}
    rec = Recorder()

    async def fetch(url):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("flaky")
        return b"ok"

    out = run(fetch_all(["u"], fetch, retries=3, backoff=0.5, sleep=rec))
    assert out["u"] == Result(True, b"ok", None, 3)
    assert rec.sleeps == [0.5, 1.0]


def test_retries_exhausted():
    rec = Recorder()

    async def fetch(url):
        raise TransientError("boom")

    out = run(fetch_all(["u"], fetch, retries=2, backoff=0.1, sleep=rec))
    r = out["u"]
    assert r.ok is False and r.data is None and r.attempts == 3
    assert r.error == "TransientError: boom"
    assert rec.sleeps == pytest.approx([0.1, 0.2])


def test_non_transient_not_retried():
    calls = {"n": 0}

    async def fetch(url):
        calls["n"] += 1
        raise ValueError("bad url")

    out = run(fetch_all(["u"], fetch, sleep=Recorder()))
    assert calls["n"] == 1
    assert out["u"] == Result(False, None, "ValueError: bad url", 1)


def test_timeout_is_retried():
    calls = {"n": 0}

    async def fetch(url):
        calls["n"] += 1
        if calls["n"] == 1:
            await asyncio.sleep(1)
        return b"late-ok"

    out = run(fetch_all(["u"], fetch, timeout=0.05, retries=1, sleep=Recorder()))
    assert out["u"].ok and out["u"].attempts == 2


def test_timeout_error_message():
    async def fetch(url):
        await asyncio.sleep(1)

    out = run(fetch_all(["u"], fetch, timeout=0.02, retries=0, sleep=Recorder()))
    assert out["u"].ok is False and out["u"].error.startswith("TimeoutError")


def test_duplicates_fetched_once():
    seen = []

    async def fetch(url):
        seen.append(url)
        return b""

    out = run(fetch_all(["a", "b", "a", "c", "b"], fetch))
    assert list(out) == ["a", "b", "c"]
    assert sorted(seen) == ["a", "b", "c"]


def test_failure_isolated():
    async def fetch(url):
        if url == "bad":
            raise RuntimeError("x")
        return b"fine"

    out = run(fetch_all(["bad", "good"], fetch))
    assert out["good"].ok and not out["bad"].ok


def test_backoff_does_not_hold_slot():
    # one URL keeps failing and sleeping; with concurrency=1 the others must still progress
    order = []

    async def main():
        released = asyncio.Event()

        async def sleep(s):
            await released.wait()

        async def fetch(url):
            order.append(url)
            if url == "flaky":
                raise TransientError("again")
            if len([u for u in order if u != "flaky"]) == 3:
                released.set()
            return b""

        return await asyncio.wait_for(
            fetch_all(["flaky", "a", "b", "c"], fetch, concurrency=1, retries=1, sleep=sleep), 2)

    out = run(main())
    assert out["a"].ok and out["b"].ok and out["c"].ok
    assert out["flaky"].attempts == 2
