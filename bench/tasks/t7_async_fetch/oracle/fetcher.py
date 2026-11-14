import asyncio
from dataclasses import dataclass
from typing import Optional


class TransientError(Exception):
    pass


@dataclass
class Result:
    ok: bool
    data: Optional[bytes]
    error: Optional[str]
    attempts: int


def _describe(exc):
    if isinstance(exc, asyncio.TimeoutError):
        return f"TimeoutError: {exc or 'timed out'}"
    return f"{type(exc).__name__}: {exc}"


async def fetch_all(urls, fetch, *, concurrency=5, retries=3, backoff=0.1,
                    timeout=2.0, sleep=asyncio.sleep):
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    unique = list(dict.fromkeys(urls))
    sem = asyncio.Semaphore(concurrency)

    async def one(url):
        attempt = 0
        while True:
            attempt += 1
            try:
                async with sem:
                    data = await asyncio.wait_for(fetch(url), timeout)
                return Result(True, data, None, attempt)
            except (TransientError, asyncio.TimeoutError) as e:
                if attempt > retries:
                    return Result(False, None, _describe(e), attempt)
                await sleep(backoff * 2 ** (attempt - 1))
            except Exception as e:
                return Result(False, None, _describe(e), attempt)

    results = await asyncio.gather(*(one(u) for u in unique))
    return dict(zip(unique, results, strict=True))
