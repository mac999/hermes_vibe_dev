"""Allocate orders to stock lots.

Rules
- Orders are processed in the given order.
- For each order, lots of the same SKU are used in FEFO order: earliest
  expiry first; ties broken by lot_id ascending.
- Lots whose expiry is before the order's ship_date are never used.
- An order may be split across several lots and may be partially filled.
- Return (allocations, remaining):
    allocations: list of (order_id, [(lot_id, qty), ...]) in input order,
                 including orders that got nothing (empty list).
    remaining:   dict lot_id -> qty left, for every lot.
"""
from collections import namedtuple

Order = namedtuple("Order", "order_id sku qty ship_date")
Lot = namedtuple("Lot", "lot_id sku qty expiry")


def allocate(orders, lots):
    remaining = {lot.lot_id: lot.qty for lot in lots}
    allocations = []
    for order in orders:
        need = order.qty
        picks = []
        candidates = []
        for lot in lots:
            if lot.sku == order.sku and lot.expiry >= order.ship_date:
                candidates.append(lot)
        candidates.sort(key=lambda l: (l.expiry, l.lot_id))
        for lot in candidates:
            if need == 0:
                break
            have = remaining[lot.lot_id]
            if have == 0:
                continue
            take = min(have, need)
            remaining[lot.lot_id] = have - take
            need -= take
            picks.append((lot.lot_id, take))
        allocations.append((order.order_id, picks))
    return allocations, remaining
