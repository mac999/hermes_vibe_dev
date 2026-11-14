import copy
import random
import time
from datetime import date, timedelta

from allocator import Lot, Order, allocate

BASE = date(2026, 1, 1)


def reference(orders, lots):
    remaining = {lot.lot_id: lot.qty for lot in lots}
    allocations = []
    for order in orders:
        need = order.qty
        picks = []
        cands = sorted((l for l in lots if l.sku == order.sku and l.expiry >= order.ship_date),
                       key=lambda l: (l.expiry, l.lot_id))
        for lot in cands:
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


def gen(n_orders, n_lots, n_skus, seed, ship_sorted=False):
    rnd = random.Random(seed)
    skus = [f"S{i}" for i in range(n_skus)]
    lots = [Lot(f"L{i:06d}", rnd.choice(skus), rnd.randint(0, 20), BASE + timedelta(days=rnd.randint(0, 60)))
            for i in range(n_lots)]
    rnd.shuffle(lots)
    days = [rnd.randint(0, 70) for _ in range(n_orders)]
    if ship_sorted:
        days.sort()
    orders = [Order(f"o{i}", rnd.choice(skus), rnd.randint(0, 15), BASE + timedelta(days=d))
              for i, d in enumerate(days)]
    return orders, lots


def test_equivalence_random_small():
    for seed in range(40):
        orders, lots = gen(60, 40, 4, seed)
        assert allocate(orders, lots) == reference(orders, lots), seed


def test_equivalence_ship_dates_not_monotonic():
    # later orders with an earlier ship_date can still use lots that earlier orders skipped
    for seed in range(40, 60):
        orders, lots = gen(300, 120, 3, seed)
        assert allocate(orders, lots) == reference(orders, lots), seed


def test_equivalence_ties_and_zero_qty():
    d = date(2026, 3, 1)
    lots = [Lot("b", "A", 2, d), Lot("a", "A", 0, d), Lot("c", "A", 2, d), Lot("z", "C", 1, d)]
    orders = [Order("o1", "A", 3, d), Order("o2", "A", 0, d), Order("o3", "A", 5, d),
              Order("o4", "B", 1, d), Order("o5", "A", 1, d + timedelta(days=1))]
    assert allocate(orders, lots) == reference(orders, lots)


def test_inputs_not_mutated():
    orders, lots = gen(200, 100, 5, 7)
    o2, l2 = copy.deepcopy(orders), copy.deepcopy(lots)
    allocate(orders, lots)
    assert orders == o2 and lots == l2


def test_large_is_fast():
    orders, lots = gen(200_000, 50_000, 2_000, 123)
    t = time.perf_counter()
    alloc, rem = allocate(orders, lots)
    elapsed = time.perf_counter() - t
    assert len(alloc) == 200_000 and len(rem) == 50_000
    assert elapsed < 2.0, f"{elapsed:.2f}s"


def test_large_matches_sample_of_reference():
    # spot-check the large run against the reference on a subset of SKUs
    orders, lots = gen(20_000, 5_000, 50, 99)
    keep = {f"S{i}" for i in range(5)}
    so = [o for o in orders if o.sku in keep]
    sl = [l for l in lots if l.sku in keep]
    full_alloc, full_rem = allocate(orders, lots)
    ref_alloc, ref_rem = reference(so, sl)
    got = [a for a, o in zip(full_alloc, orders) if o.sku in keep]
    assert got == ref_alloc
    assert {k: v for k, v in full_rem.items() if k in ref_rem} == ref_rem
