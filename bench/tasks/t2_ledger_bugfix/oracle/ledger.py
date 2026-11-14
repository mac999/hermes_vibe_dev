"""Simple account ledger."""
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


class InsufficientFunds(Exception):
    pass


@dataclass
class Entry:
    day: date
    account: str
    amount: Decimal
    memo: str = ""


def _money(amount):
    if isinstance(amount, float):
        amount = str(amount)
    return Decimal(amount).quantize(_CENT, rounding=ROUND_HALF_UP)


class Ledger:
    def __init__(self):
        self._entries = []
        self._accounts = set()

    def open(self, account):
        if account in self._accounts:
            raise ValueError(f"account exists: {account}")
        self._accounts.add(account)

    def _check(self, account):
        if account not in self._accounts:
            raise KeyError(account)

    def _positive(self, amount):
        amount = _money(amount)
        if amount <= 0:
            raise ValueError("amount must be positive")
        return amount

    def deposit(self, account, amount, day, memo=""):
        self._check(account)
        self._entries.append(Entry(day, account, self._positive(amount), memo))

    def withdraw(self, account, amount, day, memo=""):
        self._check(account)
        amount = self._positive(amount)
        if amount > self.balance(account):
            raise InsufficientFunds(f"{account}: {amount}")
        self._entries.append(Entry(day, account, -amount, memo))

    def transfer(self, src, dst, amount, day, memo=""):
        if src == dst:
            raise ValueError("cannot transfer to the same account")
        self._check(src)
        self._check(dst)
        amount = self._positive(amount)
        if amount > self.balance(src):
            raise InsufficientFunds(f"{src}: {amount}")
        self._entries.append(Entry(day, src, -amount, memo or f"to {dst}"))
        self._entries.append(Entry(day, dst, amount, memo or f"from {src}"))

    def balance(self, account):
        self._check(account)
        return sum((e.amount for e in self._entries if e.account == account), Decimal("0.00"))

    def balance_at(self, account, day):
        self._check(account)
        return sum(
            (e.amount for e in self._entries if e.account == account and e.day <= day),
            Decimal("0.00"),
        )

    def history(self, account):
        self._check(account)
        return [e for e in self._entries if e.account == account]
