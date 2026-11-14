# 과제: 메모 REST API (Flask)

`app.py` 에 Flask 앱 팩토리 `create_app()` 를 만들어 메모(note) REST API 를 구현해 주세요. 저장소는 메모리로 충분합니다(앱 인스턴스마다 독립). Flask 외 추가 패키지는 쓰지 않습니다.

## 메모 객체

```json
{"id": 1, "title": "...", "body": "...", "tags": ["a", "b"], "created_at": "2026-11-08T10:00:00Z"}
```

- `id` 는 1부터 증가하는 정수, 삭제돼도 재사용하지 않습니다.
- `created_at` 은 UTC ISO8601, 끝에 `Z`.

## 엔드포인트

- `POST /notes` — JSON 본문. `title` 필수(앞뒤 공백 제거 후 1~100자 문자열), `body` 선택(문자열, 기본 ""), `tags` 선택(문자열 리스트, 기본 [], 중복 제거하되 처음 순서 유지). 성공 시 201, 메모 JSON, `Location: /notes/<id>` 헤더.
- `GET /notes` — 목록. 쿼리: `tag`(그 태그를 가진 것만), `q`(title 또는 body 에 대소문자 무시 부분일치), `page`(기본 1), `per_page`(기본 10, 최대 50). 응답 `{"items": [...], "page": p, "per_page": n, "total": 전체 일치 개수}`. id 오름차순. page/per_page 가 정수가 아니거나 1 미만이거나 per_page 가 50 초과면 400.
- `GET /notes/<id>` — 200 또는 404.
- `PATCH /notes/<id>` — `title`, `body`, `tags` 중 보낸 필드만 수정(검증 규칙 동일). 알 수 없는 필드가 있으면 400. 200 과 수정된 메모.
- `DELETE /notes/<id>` — 204, 본문 없음. 없으면 404.

## 오류

- 모든 오류 응답은 JSON `{"error": "<설명>"}` 와 해당 상태 코드. 없는 경로의 404 도 JSON 이어야 합니다.
- JSON 이 아닌 본문이나 JSON 객체가 아닌 본문은 400.

테스트도 함께 작성해 주세요.
