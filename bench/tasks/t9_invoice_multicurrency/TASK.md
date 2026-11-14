# 과제: 청구서 패키지 버그 수정과 다중 통화 지원

현재 폴더는 `invoicing` 패키지(청구서 모델, 세금, 할인, 합계 계산, 저장, 출력, CLI)와 그 테스트(`tests/`)입니다. 먼저 코드 전체 구조를 파악한 뒤 아래 작업을 해 주세요. 기존 테스트(`python -m pytest tests`)는 계속 통과해야 하고, 지우거나 약하게 바꾸면 안 됩니다.

## 1. 버그 수정 — 쿠폰 할인이 세금에 반영되지 않음

고객 리포트: 쿠폰을 쓰면 할인은 되는데 세금은 할인 전 금액 기준으로 매겨진다. 할인은 세전에 적용되어야 한다.

- 세금은 (과세 품목 금액 − 그 품목들에 배분된 쿠폰 할인) × 세율 로 계산합니다.
- 쿠폰 할인은 과세·비과세 품목에 **금액 비율대로** 배분합니다. 예: 소계 30,000 중 과세 20,000, 비과세 10,000 이고 할인이 3,000 이면 과세분에서 2,000 을 뺍니다.
- 볼륨 할인(수량 10개 이상 5%)과 쿠폰 규칙 자체는 바꾸지 않습니다.

## 2. 다중 통화

- `Invoice` 에 `currency` 필드 추가(기본값 `"KRW"`). 지원 통화: `KRW`, `JPY`(소수점 없음), `USD`, `EUR`(소수점 둘째 자리). 그 외는 `ValueError`.
- 품목 단가는 청구서 통화 기준 금액입니다.
- `totals()` 의 subtotal, discount, tax, total 은 각각 해당 통화의 최소 단위로 ROUND_HALF_UP 반올림하고, total = subtotal − discount + tax 입니다(반올림된 값끼리 계산).
- 정액 쿠폰(`FLAT5000`, `FLAT1000`)의 금액은 원화 기준입니다. 원화가 아닌 청구서에서는 환율로 환산해 적용합니다. 환율이 없으면 정액 쿠폰이 있는 원화 외 청구서는 `ValueError`.
- 새 모듈 `invoicing/fx.py`
  - `convert(amount, src, dst, rates) -> Decimal`: `rates` 는 `{"USD": Decimal("1350"), ...}` 처럼 **해당 통화 1단위가 원화로 얼마인지**를 담은 dict 이고 KRW 는 1 로 간주합니다. 결과는 `dst` 의 최소 단위로 ROUND_HALF_UP. 모르는 통화나 rates 에 없는 통화는 `ValueError`.
  - `load_rates(path) -> dict`: `{"USD": "1350.00", "EUR": "1480.5", "JPY": "9.12"}` 형식 JSON 을 읽어 Decimal 값 dict 로.
- `totals(invoice, rates=None)` 로 환율을 받을 수 있게 하되, 기존 호출 `totals(invoice)` 는 그대로 동작해야 합니다.
- 금액 표시(`render.money`)는 통화 기호와 천 단위 구분: `₩1,234`, `¥1,234`, `$1,234.50`, `€1,234.50`. 음수는 `-$12.30` 처럼 기호 앞에 부호. `money(amount)` 처럼 통화를 생략하면 KRW 입니다.
- `render_text` 와 CLI `list` 는 청구서 자기 통화로 표시합니다.
- 저장: `currency` 를 저장하고, 예전 형식(통화 필드 없음) 파일은 KRW 로 읽습니다.
- CLI
  - `create` 의 spec JSON 에 `"currency"` 를 받을 수 있고(없으면 KRW), 정액 쿠폰이 있는 원화 외 청구서를 위해 `--rates FILE` 옵션을 받습니다.
  - `total NUMBER [--in CUR --rates FILE]`: `--in` 이 있으면 청구서 total 을 그 통화로 환산해 출력합니다. `--in` 만 있고 `--rates` 가 없거나 통화를 모르면 stderr 에 `error` 를 포함한 메시지와 종료 코드 1.

새 기능과 버그 수정에 대한 테스트도 `tests/` 에 추가해 주세요.
