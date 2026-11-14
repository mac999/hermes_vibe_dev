import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

DECIMALS = {"KRW": 0, "JPY": 0, "USD": 2, "EUR": 2}
SYMBOLS = {"KRW": "₩", "JPY": "¥", "USD": "$", "EUR": "€"}


def check_currency(code: str) -> str:
    if code not in DECIMALS:
        raise ValueError(f"unsupported currency: {code}")
    return code


def quantize(amount, currency: str) -> Decimal:
    exp = Decimal(1).scaleb(-DECIMALS[check_currency(currency)])
    return Decimal(amount).quantize(exp, rounding=ROUND_HALF_UP)


def krw_per_unit(currency: str, rates) -> Decimal:
    check_currency(currency)
    if currency == "KRW":
        return Decimal(1)
    if not rates or currency not in rates:
        raise ValueError(f"no exchange rate for {currency}")
    return Decimal(rates[currency])


def convert_exact(amount, src: str, dst: str, rates) -> Decimal:
    return Decimal(amount) * krw_per_unit(src, rates) / krw_per_unit(dst, rates)


def convert(amount, src: str, dst: str, rates) -> Decimal:
    return quantize(convert_exact(amount, src, dst, rates), dst)


def load_rates(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {code: Decimal(str(value)) for code, value in data.items()}
