# 과제: TTL + LRU 캐시

현재 폴더에 `cache.py` 를 만들고 `TTLCache` 클래스를 구현해 주세요. 외부 패키지 없이 표준 라이브러리만 씁니다.

## 인터페이스

```python
TTLCache(capacity: int, ttl: float, clock=time.monotonic)
```

- `capacity` 가 1 미만이거나 `ttl` 이 0 이하이면 `ValueError`.
- `clock` 은 현재 시각(초, float)을 돌려주는 함수. 테스트에서 가짜 시계를 넣습니다.

메서드

- `put(key, value)` — 저장. 이미 있는 키면 값을 바꾸고 만료 시각을 새로 시작하며 가장 최근 사용으로 만듭니다.
- `get(key, default=None)` — 값 반환. 만료됐거나 없으면 `default`. 성공한 `get` 은 그 키를 가장 최근 사용으로 만들지만 만료 시각은 늘리지 않습니다.
- `delete(key) -> bool` — 지웠으면 True, 없었거나 이미 만료였으면 False.
- `len(cache)` — 만료되지 않은 항목 수.
- `key in cache` — 만료되지 않은 항목이 있으면 True. 이 검사는 사용 순서를 바꾸지 않습니다.

## 규칙

- 항목은 `put` 시각 + `ttl` 에 도달하는 순간부터 만료입니다 (`now >= put_time + ttl` 이면 만료).
- 용량을 넘기면 먼저 만료된 항목을 모두 버리고, 그래도 넘치면 가장 오래 사용되지 않은 항목을 버립니다.
- `None` 도 정상적인 값으로 저장할 수 있어야 합니다.

테스트 코드도 함께 작성해 주세요.
