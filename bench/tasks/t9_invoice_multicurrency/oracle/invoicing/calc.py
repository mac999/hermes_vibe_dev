from decimal import Decimal

from invoicing.discounts import coupon_discount, line_net
from invoicing.fx import check_currency, quantize
from invoicing.tax import tax_rate


def totals(invoice, rates=None) -> dict:
    """Return subtotal, discount, tax and total in the invoice currency.

    Coupon discounts are applied before tax and split between taxable and
    non-taxable lines in proportion to their amounts.
    """
    cur = check_currency(getattr(invoice, "currency", "KRW") or "KRW")
    nets = [(item, line_net(item)) for item in invoice.items]
    subtotal = sum((n for _, n in nets), Decimal("0"))
    taxable = sum((n for item, n in nets if item.taxable), Decimal("0"))
    discount = coupon_discount(invoice.coupons, subtotal, cur, rates)
    taxable_after = taxable - (discount * taxable / subtotal if subtotal else Decimal("0"))
    tax = taxable_after * tax_rate(invoice.customer)
    subtotal, discount, tax = quantize(subtotal, cur), quantize(discount, cur), quantize(tax, cur)
    return {"subtotal": subtotal, "discount": discount, "tax": tax, "total": subtotal - discount + tax}
