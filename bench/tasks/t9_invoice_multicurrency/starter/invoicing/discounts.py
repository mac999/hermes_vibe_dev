from decimal import Decimal

# code -> (kind, value). Fixed amounts are in KRW.
COUPONS = {
    "WELCOME10": ("percent", Decimal("10")),
    "VIP20": ("percent", Decimal("20")),
    "FLAT5000": ("fixed", Decimal("5000")),
    "FLAT1000": ("fixed", Decimal("1000")),
}

VOLUME_MIN_QTY = 10
VOLUME_RATE = Decimal("0.05")


def line_net(item) -> Decimal:
    """Line amount after the volume discount (5% off when quantity >= 10)."""
    gross = item.gross
    if item.quantity >= VOLUME_MIN_QTY:
        return gross - gross * VOLUME_RATE
    return gross


def coupon_discount(codes, base: Decimal) -> Decimal:
    """Discount for a list of coupon codes on `base`.

    Percent coupons do not stack: only the largest one applies, to the base.
    Fixed coupons stack. The total discount never exceeds the base.
    Unknown codes raise ValueError.
    """
    best_percent = Decimal("0")
    fixed = Decimal("0")
    for code in codes:
        if code not in COUPONS:
            raise ValueError(f"unknown coupon: {code}")
        kind, value = COUPONS[code]
        if kind == "percent":
            best_percent = max(best_percent, value)
        else:
            fixed += value
    discount = base * best_percent / 100 + fixed
    return min(discount, base)
