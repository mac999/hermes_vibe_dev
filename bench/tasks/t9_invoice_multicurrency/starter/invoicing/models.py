from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class Customer:
    name: str
    region: str  # "KR", "US-CA", "US-NY", "DE", "FR"
    vat_id: Optional[str] = None  # EU business customers only


@dataclass
class LineItem:
    sku: str
    description: str
    unit_price: Decimal
    quantity: int
    taxable: bool = True

    @property
    def gross(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Invoice:
    number: str
    customer: Customer
    issued: date
    items: list = field(default_factory=list)
    coupons: list = field(default_factory=list)
