from datetime import date

from ledger import Ledger


def test_deposit_and_balance():
    lg = Ledger()
    lg.open("a")
    lg.deposit("a", 100, date(2026, 1, 1))
    assert lg.balance("a") == 100


def test_history_order():
    lg = Ledger()
    lg.open("a")
    lg.deposit("a", 5, date(2026, 1, 1), "first")
    lg.deposit("a", 7, date(2026, 1, 2), "second")
    assert [e.memo for e in lg.history("a")] == ["first", "second"]
