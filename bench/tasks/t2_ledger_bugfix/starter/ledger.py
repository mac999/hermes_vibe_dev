"""Simple account ledger."""
from dataclasses import dataclass
from datetime import date


class InsufficientFunds(Exception):
    pass


@dataclass
class Entry:
    day: date
    account: str
    amount: float
    memo: str = ""


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

    def deposit(self, account, amount, day, memo=""):
        self._check(account)
        amount = float(amount)
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._entries.append(Entry(day, account, amount, memo))

    def withdraw(self, account, amount, day, memo=""):
        self._check(account)
        amount = float(amount)
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._entries.append(Entry(day, account, -amount, memo))

    def transfer(self, src, dst, amount, day, memo=""):
        self.withdraw(src, amount, day, memo or f"to {dst}")
        self.deposit(dst, amount, day, memo or f"from {src}")

    def balance(self, account):
        self._check(account)
        return sum(e.amount for e in self._entries if e.account == account)

    def balance_at(self, account, day):
        self._check(account)
        return sum(e.amount for e in self._entries if e.account == account and e.day < day)

    def history(self, account):
        self._check(account)
        return [e for e in self._entries if e.account == account]
