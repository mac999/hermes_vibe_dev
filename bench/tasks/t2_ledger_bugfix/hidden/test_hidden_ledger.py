from datetime import date
from decimal import Decimal

import pytest

from ledger import InsufficientFunds, Ledger

D1, D2, D3 = date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)


@pytest.fixture
def lg():
    lg = Ledger()
    lg.open("a")
    lg.open("b")
    return lg


def test_balance_is_decimal(lg):
    lg.deposit("a", 10, D1)
    assert isinstance(lg.balance("a"), Decimal)
    assert lg.balance("a") == Decimal("10.00")


def test_decimal_precision_many_transfers(lg):
    lg.deposit("a", "1.00", D1)
    for _ in range(10):
        lg.transfer("a", "b", "0.10", D1)
    assert lg.balance("a") == Decimal("0.00")
    assert lg.balance("b") == Decimal("1.00")


def test_round_half_up(lg):
    lg.deposit("a", "0.005", D1)
    assert lg.balance("a") == Decimal("0.01")
    lg.deposit("b", Decimal("2.345"), D1)
    assert lg.balance("b") == Decimal("2.35")


def test_amount_accepts_int_str_decimal(lg):
    lg.deposit("a", 1, D1)
    lg.deposit("a", "2.50", D1)
    lg.deposit("a", Decimal("0.25"), D1)
    assert lg.balance("a") == Decimal("3.75")


def test_same_account_transfer_rejected(lg):
    lg.deposit("a", 10, D1)
    with pytest.raises(ValueError):
        lg.transfer("a", "a", 5, D1)
    assert lg.balance("a") == Decimal("10")
    assert len(lg.history("a")) == 1


def test_balance_at_includes_that_day(lg):
    lg.deposit("a", 10, D1)
    lg.deposit("a", 5, D2)
    lg.deposit("a", 1, D3)
    assert lg.balance_at("a", D1) == Decimal("10")
    assert lg.balance_at("a", D2) == Decimal("15")
    assert lg.balance_at("a", date(2026, 2, 28)) == Decimal("0")


def test_withdraw_insufficient(lg):
    lg.deposit("a", 10, D1)
    with pytest.raises(InsufficientFunds):
        lg.withdraw("a", "10.01", D1)
    assert lg.balance("a") == Decimal("10")
    assert len(lg.history("a")) == 1


def test_withdraw_exact_balance_ok(lg):
    lg.deposit("a", "10.00", D1)
    lg.withdraw("a", 10, D1)
    assert lg.balance("a") == Decimal("0")


def test_transfer_insufficient_is_atomic(lg):
    lg.deposit("a", 5, D1)
    with pytest.raises(InsufficientFunds):
        lg.transfer("a", "b", 6, D1)
    assert lg.balance("a") == Decimal("5")
    assert lg.balance("b") == Decimal("0")
    assert lg.history("b") == []


def test_transfer_to_unknown_account_is_atomic(lg):
    lg.deposit("a", 5, D1)
    with pytest.raises(KeyError):
        lg.transfer("a", "nope", 1, D1)
    assert lg.balance("a") == Decimal("5")


def test_api_unchanged(lg):
    lg.deposit("a", 3, D1, "memo-x")
    e = lg.history("a")[0]
    assert e.day == D1 and e.account == "a" and e.memo == "memo-x"
    assert e.amount == Decimal("3")
    with pytest.raises(ValueError):
        lg.open("a")
    with pytest.raises(KeyError):
        lg.balance("zzz")
    with pytest.raises(ValueError):
        lg.deposit("a", 0, D1)
    with pytest.raises(ValueError):
        lg.withdraw("a", "-1", D1)


def test_transfer_memo_defaults(lg):
    lg.deposit("a", 5, D1)
    lg.transfer("a", "b", 1, D2)
    assert lg.history("a")[-1].memo == "to b"
    assert lg.history("b")[-1].memo == "from a"
    assert lg.history("b")[-1].amount == Decimal("1")
