from invoicing.calc import totals


def money(amount) -> str:
    return f"₩{int(amount):,}"


def render_text(inv) -> str:
    t = totals(inv)
    lines = [f"Invoice {inv.number}  {inv.issued.isoformat()}", f"Bill to: {inv.customer.name} ({inv.customer.region})", ""]
    for item in inv.items:
        lines.append(f"  {item.sku:<8} {item.description:<24} {item.quantity:>4} x {money(item.unit_price)}")
    lines += [
        "",
        f"  Subtotal: {money(t['subtotal'])}",
        f"  Discount: -{money(t['discount'])}",
        f"  Tax:      {money(t['tax'])}",
        f"  Total:    {money(t['total'])}",
    ]
    return "\n".join(lines)
