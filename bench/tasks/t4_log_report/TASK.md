# 과제: 웹 접근 로그 요약 리포트

`report.py` 를 만들어 주세요. 표준 라이브러리만 씁니다. 예시 입력은 `sample.log` 에 있습니다.

## 로그 한 줄 형식

```
<ip> - - [<dd/Mon/yyyy:HH:MM:SS +zzzz>] "<METHOD> <path> <protocol>" <status> <bytes> <latency_ms>
```

예: `10.0.0.1 - - [07/Nov/2026:23:59:58 +0900] "GET /api/items?page=2 HTTP/1.1" 200 512 37`

- `bytes` 는 `-` 일 수 있습니다(0으로 취급).
- 이 형식에 맞지 않는 줄(빈 줄 포함)은 malformed 로 세고 건너뜁니다. 상태 코드가 100~599 범위가 아니거나 latency 가 음수가 아닌 정수가 아니면 malformed 입니다.

## 함수

`summarize(lines, top=5) -> dict` 는 문자열 줄들의 iterable 을 받아 다음 키를 가진 dict 를 돌려줍니다.

- `total`: 정상 줄 수
- `malformed`: malformed 줄 수
- `status_classes`: `{"2xx": n, "3xx": n, "4xx": n, "5xx": n}` (100번대는 `"1xx"`; 0인 클래스도 4개 키는 항상 포함, 1xx 는 있을 때만)
- `top_paths`: 쿼리스트링(`?` 뒤)을 뗀 경로별 요청 수 상위 `top` 개. `[[path, count], ...]` 형태, 개수 내림차순, 같으면 경로 사전순
- `latency_ms`: `{"p50": x, "p95": x, "max": x}` — nearest-rank 방식 백분위수(정렬 후 `ceil(p/100 * n)` 번째 값, 1부터 셈). 정상 줄이 없으면 세 값 모두 `None`
- `bytes_total`: 바이트 합계
- `requests_per_hour_utc`: UTC 로 변환한 시각의 `"YYYY-MM-DDTHH"` 를 키로 한 요청 수 dict

## CLI

`python report.py <logfile> [--top N]` → 위 dict 를 JSON 으로 stdout 에 출력(키 순서 무관, `indent=2`). 파일이 없으면 stderr 에 메시지, 종료 코드 1.

테스트도 함께 작성해 주세요.
