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
from bisect import bisect_left
from collections import defaultdict, namedtuple

Order = namedtuple("Order", "order_id sku qty ship_date")
Lot = namedtuple("Lot", "lot_id sku qty expiry")


def allocate(orders, lots):
    remaining = {lot.lot_id: lot.qty for lot in lots}
    by_sku = defaultdict(list)
    for lot in lots:
        by_sku[lot.sku].append(lot)
    index = {}
    for sku, group in by_sku.items():
        group.sort(key=lambda l: (l.expiry, l.lot_id))
        ids = [l.lot_id for l in group]
        expiries = [l.expiry for l in group]
        # nxt[i]: first index >= i whose lot may still have stock (path-compressed)
        index[sku] = (ids, expiries, list(range(len(group) + 1)))

    def find(nxt, i):
        root = i
        while nxt[root] != root:
            root = nxt[root]
        while nxt[i] != root:
            nxt[i], i = root, nxt[i]
        return root

    allocations = []
    for order in orders:
        picks = []
        need = order.qty
        entry = index.get(order.sku)
        if entry and need > 0:
            ids, expiries, nxt = entry
            i = find(nxt, bisect_left(expiries, order.ship_date))
            while need > 0 and i < len(ids):
                lot_id = ids[i]
                have = remaining[lot_id]
                if have:
                    take = min(have, need)
                    remaining[lot_id] = have - take
                    need -= take
                    picks.append((lot_id, take))
                if remaining[lot_id] == 0:
                    nxt[i] = i + 1
                    i = find(nxt, i + 1)
                else:
                    break
        allocations.append((order.order_id, picks))
    return allocations, remaining
