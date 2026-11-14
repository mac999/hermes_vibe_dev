from decimal import ROUND_HALF_UP, Decimal

from invoicing.discounts import coupon_discount, line_net
from invoicing.tax import tax_rate


def _won(x: Decimal) -> Decimal:
    return x.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def totals(invoice) -> dict:
    """Return subtotal, discount, tax and total for an invoice (all KRW)."""
    nets = [(item, line_net(item)) for item in invoice.items]
    subtotal = sum((n for _, n in nets), Decimal("0"))
    taxable = sum((n for item, n in nets if item.taxable), Decimal("0"))
    discount = coupon_discount(invoice.coupons, subtotal)
    tax = taxable * tax_rate(invoice.customer)
    subtotal, discount, tax = _won(subtotal), _won(discount), _won(tax)
    return {
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "total": subtotal - discount + tax,
    }
