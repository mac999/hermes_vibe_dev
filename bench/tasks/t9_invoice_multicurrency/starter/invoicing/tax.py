from decimal import Decimal

RATES = {
    "KR": Decimal("0.10"),
    "US-CA": Decimal("0.0725"),
    "US-NY": Decimal("0.04"),
    "DE": Decimal("0.19"),
    "FR": Decimal("0.20"),
}
EU = {"DE", "FR"}


def is_reverse_charge(customer) -> bool:
    """EU business customers with a VAT id pay the VAT themselves."""
    return customer.region in EU and bool(customer.vat_id)


def tax_rate(customer) -> Decimal:
    if is_reverse_charge(customer):
        return Decimal("0")
    try:
        return RATES[customer.region]
    except KeyError:
        raise ValueError(f"unknown region: {customer.region}") from None
