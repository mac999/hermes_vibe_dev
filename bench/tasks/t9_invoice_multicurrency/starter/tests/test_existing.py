import json
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from invoicing.calc import totals
from invoicing.discounts import coupon_discount, line_net
from invoicing.models import Customer, Invoice, LineItem
from invoicing.render import render_text
from invoicing.storage import Store
from invoicing.tax import tax_rate

ROOT = Path(__file__).resolve().parents[1]
KR = Customer("Acme", "KR")


def inv(items, coupons=(), customer=KR):
    return Invoice("INV-2026-0001", customer, date(2026, 3, 1), list(items), list(coupons))


def item(price, qty=1, taxable=True, sku="A"):
    return LineItem(sku, "thing", Decimal(price), qty, taxable)


def test_simple_kr():
    t = totals(inv([item("10000", 2)]))
    assert t == {"subtotal": Decimal("20000"), "discount": Decimal("0"), "tax": Decimal("2000"), "total": Decimal("22000")}


def test_volume_discount():
    assert line_net(item("1000", 10)) == Decimal("9500")
    assert line_net(item("1000", 9)) == Decimal("9000")


def test_non_taxable_line():
    t = totals(inv([item("10000"), item("5000", taxable=False, sku="B")]))
    assert t["tax"] == Decimal("1000") and t["total"] == Decimal("16000")


def test_tax_rates():
    assert tax_rate(Customer("x", "US-CA")) == Decimal("0.0725")
    assert tax_rate(Customer("x", "DE", vat_id="DE123")) == Decimal("0")
    with pytest.raises(ValueError):
        tax_rate(Customer("x", "MARS"))


def test_coupon_rules():
    base = Decimal("100000")
    assert coupon_discount(["WELCOME10", "VIP20"], base) == Decimal("20000")
    assert coupon_discount(["FLAT5000", "FLAT1000"], base) == Decimal("6000")
    assert coupon_discount(["FLAT5000"], Decimal("3000")) == Decimal("3000")
    with pytest.raises(ValueError):
        coupon_discount(["NOPE"], base)


def test_storage_roundtrip_and_numbering(tmp_path):
    s = Store(tmp_path / "db.json")
    assert s.next_number(2026) == "INV-2026-0001"
    s.add(inv([item("100")]))
    assert s.next_number(2026) == "INV-2026-0002"
    got = s.get("INV-2026-0001")
    assert got.items[0].unit_price == Decimal("100") and got.customer.region == "KR"
    with pytest.raises(ValueError):
        s.add(inv([item("1")]))


def test_render_text():
    out = render_text(inv([item("1234567")]))
    assert "Total:    ₩1,358,024" in out


def test_cli_create_and_total(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"issued": "2026-04-02", "customer": {"name": "Kim", "region": "KR"},
                                "items": [{"sku": "S1", "description": "svc", "unit_price": 50000, "quantity": 1}]}))
    db = str(tmp_path / "db.json")
    run = lambda *a: subprocess.run([sys.executable, "-m", "invoicing", "--db", db, *a],
                                     capture_output=True, text=True, cwd=ROOT)
    assert run("create", str(spec)).stdout.strip() == "INV-2026-0001"
    assert run("total", "INV-2026-0001").stdout.strip() == "₩55,000"
    r = run("total", "INV-2026-0099")
    assert r.returncode == 1 and "error" in r.stderr
