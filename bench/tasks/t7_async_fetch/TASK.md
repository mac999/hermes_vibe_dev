# 과제: 동시성 제한과 재시도가 있는 비동기 수집기

`fetcher.py` 를 만들어 주세요. 표준 라이브러리(asyncio)만 씁니다. 실제 네트워크는 쓰지 않고, 가져오는 함수는 인자로 주입받습니다.

## 공개 요소

```python
class TransientError(Exception): ...

@dataclass
class Result:
    ok: bool
    data: bytes | None
    error: str | None
    attempts: int

async def fetch_all(urls, fetch, *, concurrency=5, retries=3, backoff=0.1,
                    timeout=2.0, sleep=asyncio.sleep) -> dict[str, Result]
```

## 동작

- `fetch` 는 `async def fetch(url) -> bytes` 형태의 함수입니다.
- 동시에 진행 중인 `fetch` 호출 수가 `concurrency` 를 절대 넘으면 안 됩니다. 1 미만이면 `ValueError`.
- 호출 한 번마다 `timeout` 초 제한. 초과하면 그 시도는 실패로 봅니다.
- `TransientError` 나 타임아웃으로 실패하면 재시도합니다. 첫 시도 포함 최대 `retries + 1` 번 시도합니다. 재시도 전 대기 시간은 `backoff * 2 ** (재시도 번호 - 1)` 초이고, 이 대기에는 반드시 주입된 `sleep` 을 씁니다(첫 재시도 전 backoff, 두 번째 전 2*backoff, ...). 대기하는 동안에는 동시성 슬롯을 차지하지 않습니다.
- 그 밖의 예외는 재시도 없이 바로 실패입니다.
- 실패한 결과의 `error` 는 마지막 예외의 클래스 이름과 메시지를 `"TransientError: boom"` 처럼 `"<클래스명>: <메시지>"` 로 담습니다. 타임아웃은 `"TimeoutError: ..."` 로 시작합니다.
- 반환 dict 의 키 순서는 입력 `urls` 의 첫 등장 순서입니다. 같은 URL 이 여러 번 있어도 한 번만 가져옵니다.
- 한 URL 의 실패가 다른 URL 처리를 막으면 안 됩니다.

테스트도 함께 작성해 주세요.
