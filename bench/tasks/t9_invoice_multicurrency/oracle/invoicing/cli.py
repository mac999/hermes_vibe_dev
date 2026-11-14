import argparse
import json
import sys
from datetime import date
from decimal import Decimal

from invoicing.calc import totals
from invoicing.fx import check_currency, convert, load_rates
from invoicing.models import Customer, Invoice, LineItem
from invoicing.render import money, render_text
from invoicing.storage import Store


def _rates(args):
    return load_rates(args.rates) if getattr(args, "rates", None) else None


def cmd_create(args, store):
    spec = json.loads(open(args.spec, encoding="utf-8").read())
    issued = date.fromisoformat(spec.get("issued", date.today().isoformat()))
    c = spec["customer"]
    inv = Invoice(
        number=store.next_number(issued.year),
        customer=Customer(c["name"], c["region"], c.get("vat_id")),
        issued=issued,
        items=[LineItem(i["sku"], i["description"], Decimal(str(i["unit_price"])), int(i["quantity"]),
                        i.get("taxable", True)) for i in spec["items"]],
        coupons=spec.get("coupons", []),
        currency=check_currency(spec.get("currency", "KRW")),
    )
    totals(inv, _rates(args))  # validate coupons/rates before saving
    store.add(inv)
    print(inv.number)
    return 0


def cmd_show(args, store):
    print(render_text(store.get(args.number), _rates(args)))
    return 0


def cmd_total(args, store):
    inv = store.get(args.number)
    rates = _rates(args)
    total = totals(inv, rates)["total"]
    if args.to:
        target = check_currency(args.to)
        if target != inv.currency and rates is None:
            raise ValueError("--in needs --rates")
        print(money(convert(total, inv.currency, target, rates), target))
    else:
        print(money(total, inv.currency))
    return 0


def cmd_list(args, store):
    rates = _rates(args)
    for inv in sorted(store.load_all(), key=lambda i: i.number):
        print(f"{inv.number}  {inv.customer.name}  {money(totals(inv, rates)['total'], inv.currency)}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="invoicing")
    p.add_argument("--db", default="invoices.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("spec")
    c.add_argument("--rates")
    c.set_defaults(func=cmd_create)
    s = sub.add_parser("show")
    s.add_argument("number")
    s.add_argument("--rates")
    s.set_defaults(func=cmd_show)
    t = sub.add_parser("total")
    t.add_argument("number")
    t.add_argument("--in", dest="to")
    t.add_argument("--rates")
    t.set_defaults(func=cmd_total)
    ls = sub.add_parser("list")
    ls.add_argument("--rates")
    ls.set_defaults(func=cmd_list)
    args = p.parse_args(argv)
    try:
        return args.func(args, Store(args.db))
    except (KeyError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
