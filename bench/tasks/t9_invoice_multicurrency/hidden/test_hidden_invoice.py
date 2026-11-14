import json
import subprocess
import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from invoicing.calc import totals
from invoicing.fx import convert, load_rates
from invoicing.models import Customer, Invoice, LineItem
from invoicing.render import money, render_text
from invoicing.storage import Store

ROOT = Path(__file__).resolve().parent
RATES = {"USD": D("1350"), "EUR": D("1480.5"), "JPY": D("9.12")}


def it(price, qty=1, taxable=True, sku="A"):
    return LineItem(sku, "thing", D(price), qty, taxable)


def inv(items, coupons=(), customer=None, currency=None):
    kw = {} if currency is None else {"currency": currency}
    return Invoice("INV-2026-0001", customer or Customer("Acme", "KR"), date(2026, 5, 1), list(items), list(coupons), **kw)


# --- bug fix: coupon discount applied before tax ---------------------------------

def test_coupon_reduces_tax_mixed_lines():
    t = totals(inv([it("20000"), it("10000", taxable=False, sku="B")], ["WELCOME10"]))
    assert t == {"subtotal": D("30000"), "discount": D("3000"), "tax": D("1800"), "total": D("28800")}


def test_fixed_coupon_reduces_tax():
    t = totals(inv([it("50000")], ["FLAT5000"]))
    assert t["tax"] == D("4500") and t["total"] == D("49500")


def test_no_coupon_unchanged():
    t = totals(inv([it("1000", 10), it("300", taxable=False)]))
    assert t == {"subtotal": D("9800"), "discount": D("0"), "tax": D("950"), "total": D("10750")}


# --- currencies ------------------------------------------------------------------

def test_default_currency_is_krw():
    assert inv([it("1")]).currency == "KRW"


def test_usd_totals_rounding():
    t = totals(inv([it("19.99", 3), it("5.00", taxable=False, sku="B")], ["WELCOME10"],
                   Customer("B", "US-CA"), "USD"))
    assert t == {"subtotal": D("64.97"), "discount": D("6.50"), "tax": D("3.91"), "total": D("62.38")}


def test_eur_fixed_coupon_converted():
    t = totals(inv([it("120.00")], ["FLAT5000"], Customer("C", "FR"), "EUR"), {"EUR": D("1250")})
    assert t == {"subtotal": D("120.00"), "discount": D("4.00"), "tax": D("23.20"), "total": D("139.20")}


def test_jpy_whole_units():
    t = totals(inv([it("1980", 2)], ["VIP20"], Customer("D", "KR"), "JPY"))
    assert t == {"subtotal": D("3960"), "discount": D("792"), "tax": D("317"), "total": D("3485")}


def test_fixed_coupon_without_rates_rejected():
    with pytest.raises(ValueError):
        totals(inv([it("10.00")], ["FLAT1000"], Customer("E", "US-NY"), "USD"))


def test_unknown_currency_rejected():
    with pytest.raises(ValueError):
        totals(inv([it("1")], currency="GBP"))


# --- fx --------------------------------------------------------------------------

def test_convert():
    assert convert(D("100"), "USD", "KRW", RATES) == D("135000")
    assert convert(D("135000"), "KRW", "USD", RATES) == D("100.00")
    assert convert(D("100"), "USD", "EUR", RATES) == D("91.19")
    assert convert(D("1000"), "KRW", "JPY", RATES) == D("110")
    assert convert(D("5"), "KRW", "KRW", {}) == D("5")


def test_convert_errors():
    with pytest.raises(ValueError):
        convert(D("1"), "GBP", "KRW", RATES)
    with pytest.raises(ValueError):
        convert(D("1"), "USD", "KRW", {"EUR": D("1480")})


def test_load_rates(tmp_path):
    f = tmp_path / "rates.json"
    f.write_text(json.dumps({"USD": "1350.00", "EUR": "1480.5", "JPY": "9.12"}))
    r = load_rates(f)
    assert r == {"USD": D("1350"), "EUR": D("1480.5"), "JPY": D("9.12")}
    assert all(isinstance(v, D) for v in r.values())


# --- formatting ------------------------------------------------------------------

@pytest.mark.parametrize("amount,cur,text", [
    (D("1234"), "KRW", "₩1,234"),
    (D("1234567"), "JPY", "¥1,234,567"),
    (D("1234.5"), "USD", "$1,234.50"),
    (D("0.5"), "EUR", "€0.50"),
    (D("-12.3"), "USD", "-$12.30"),
])
def test_money(amount, cur, text):
    assert money(amount, cur) == text


def test_money_default_krw():
    assert money(D("1234")) == "₩1,234"


def test_render_text_uses_invoice_currency():
    out = render_text(inv([it("19.99", 3), it("5.00", taxable=False, sku="B")], ["WELCOME10"],
                          Customer("B", "US-CA"), "USD"))
    assert "$62.38" in out and "₩" not in out


# --- storage ---------------------------------------------------------------------

def test_storage_currency_roundtrip(tmp_path):
    s = Store(tmp_path / "db.json")
    s.add(inv([it("9.99")], customer=Customer("U", "US-NY"), currency="USD"))
    assert s.get("INV-2026-0001").currency == "USD"


def test_storage_old_format_is_krw(tmp_path):
    db = tmp_path / "db.json"
    db.write_text(json.dumps([{"number": "INV-2025-0007", "issued": "2025-12-01",
                               "customer": {"name": "Old", "region": "KR", "vat_id": None},
                               "items": [{"sku": "X", "description": "x", "unit_price": "1000", "quantity": 1,
                                          "taxable": True}], "coupons": []}]))
    got = Store(db).get("INV-2025-0007")
    assert got.currency == "KRW" and totals(got)["total"] == D("1100")


# --- CLI -------------------------------------------------------------------------

def cli(tmp_path, *args):
    return subprocess.run([sys.executable, "-m", "invoicing", "--db", str(tmp_path / "db.json"), *args],
                          capture_output=True, text=True, cwd=ROOT)


def write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return str(p)


def test_cli_usd_total_and_conversion(tmp_path):
    spec = write(tmp_path, "spec.json", {
        "issued": "2026-05-01", "currency": "USD", "customer": {"name": "B", "region": "US-CA"},
        "items": [{"sku": "A", "description": "a", "unit_price": "19.99", "quantity": 3},
                  {"sku": "B", "description": "b", "unit_price": "5.00", "quantity": 1, "taxable": False}],
        "coupons": ["WELCOME10"]})
    rates = write(tmp_path, "rates.json", {"USD": "1350"})
    assert cli(tmp_path, "create", spec).stdout.strip() == "INV-2026-0001"
    assert cli(tmp_path, "total", "INV-2026-0001").stdout.strip() == "$62.38"
    assert cli(tmp_path, "total", "INV-2026-0001", "--in", "KRW", "--rates", rates).stdout.strip() == "₩84,213"
    assert "$62.38" in cli(tmp_path, "list").stdout


def test_cli_conversion_errors(tmp_path):
    spec = write(tmp_path, "spec.json", {"issued": "2026-05-01", "currency": "USD",
                                         "customer": {"name": "B", "region": "US-NY"},
                                         "items": [{"sku": "A", "description": "a", "unit_price": "10", "quantity": 1}]})
    cli(tmp_path, "create", spec)
    r = cli(tmp_path, "total", "INV-2026-0001", "--in", "KRW")
    assert r.returncode == 1 and "error" in r.stderr.lower()
    rates = write(tmp_path, "rates.json", {"USD": "1350"})
    r = cli(tmp_path, "total", "INV-2026-0001", "--in", "GBP", "--rates", rates)
    assert r.returncode == 1 and "error" in r.stderr.lower()


def test_cli_eur_fixed_coupon_with_rates(tmp_path):
    spec = write(tmp_path, "spec.json", {"issued": "2026-05-01", "currency": "EUR",
                                         "customer": {"name": "C", "region": "FR"},
                                         "items": [{"sku": "A", "description": "a", "unit_price": "120.00", "quantity": 1}],
                                         "coupons": ["FLAT5000"]})
    rates = write(tmp_path, "rates.json", {"EUR": "1250"})
    assert cli(tmp_path, "create", spec, "--rates", rates).returncode == 0
    assert cli(tmp_path, "total", "INV-2026-0001", "--rates", rates).stdout.strip() == "€139.20"


def test_cli_list_old_db_krw(tmp_path):
    (tmp_path / "db.json").write_text(json.dumps([{"number": "INV-2025-0001", "issued": "2025-01-02",
        "customer": {"name": "Old", "region": "KR", "vat_id": None},
        "items": [{"sku": "X", "description": "x", "unit_price": "1000", "quantity": 2, "taxable": True}],
        "coupons": []}]))
    assert "₩2,200" in cli(tmp_path, "list").stdout
