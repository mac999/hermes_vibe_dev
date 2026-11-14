from decimal import Decimal

from invoicing.calc import totals
from invoicing.fx import DECIMALS, SYMBOLS, quantize


def money(amount, currency: str = "KRW") -> str:
    value = quantize(Decimal(amount), currency)
    sign = "-" if value < 0 else ""
    return f"{sign}{SYMBOLS[currency]}{abs(value):,.{DECIMALS[currency]}f}"


def render_text(inv, rates=None) -> str:
    cur = inv.currency
    t = totals(inv, rates)
    lines = [f"Invoice {inv.number}  {inv.issued.isoformat()}", f"Bill to: {inv.customer.name} ({inv.customer.region})", ""]
    for item in inv.items:
        lines.append(f"  {item.sku:<8} {item.description:<24} {item.quantity:>4} x {money(item.unit_price, cur)}")
    lines += [
        "",
        f"  Subtotal: {money(t['subtotal'], cur)}",
        f"  Discount: -{money(t['discount'], cur)}",
        f"  Tax:      {money(t['tax'], cur)}",
        f"  Total:    {money(t['total'], cur)}",
    ]
    return "\n".join(lines)
