import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from invoicing.models import Customer, Invoice, LineItem


def _to_dict(inv: Invoice) -> dict:
    return {
        "number": inv.number,
        "issued": inv.issued.isoformat(),
        "customer": {"name": inv.customer.name, "region": inv.customer.region, "vat_id": inv.customer.vat_id},
        "items": [
            {"sku": i.sku, "description": i.description, "unit_price": str(i.unit_price),
             "quantity": i.quantity, "taxable": i.taxable}
            for i in inv.items
        ],
        "coupons": list(inv.coupons),
        "currency": inv.currency,
    }


def _from_dict(d: dict) -> Invoice:
    c = d["customer"]
    return Invoice(
        number=d["number"],
        customer=Customer(c["name"], c["region"], c.get("vat_id")),
        issued=date.fromisoformat(d["issued"]),
        items=[LineItem(i["sku"], i["description"], Decimal(i["unit_price"]), int(i["quantity"]),
                        i.get("taxable", True)) for i in d["items"]],
        coupons=list(d.get("coupons", [])),
        currency=d.get("currency", "KRW"),
    )


class Store:
    def __init__(self, path):
        self.path = Path(path)

    def load_all(self) -> list:
        if not self.path.exists():
            return []
        return [_from_dict(d) for d in json.loads(self.path.read_text(encoding="utf-8"))]

    def save_all(self, invoices) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([_to_dict(i) for i in invoices], ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, number) -> Invoice:
        for inv in self.load_all():
            if inv.number == number:
                return inv
        raise KeyError(number)

    def next_number(self, year: int) -> str:
        prefix = f"INV-{year}-"
        used = [int(i.number[len(prefix):]) for i in self.load_all() if i.number.startswith(prefix)]
        return f"{prefix}{max(used, default=0) + 1:04d}"

    def add(self, inv: Invoice) -> None:
        invoices = self.load_all()
        if any(i.number == inv.number for i in invoices):
            raise ValueError(f"duplicate invoice number: {inv.number}")
        invoices.append(inv)
        self.save_all(invoices)
