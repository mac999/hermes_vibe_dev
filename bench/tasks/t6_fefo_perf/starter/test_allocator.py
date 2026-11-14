from datetime import date

from allocator import Lot, Order, allocate


def test_fefo_split_and_partial():
    lots = [
        Lot("L2", "A", 5, date(2026, 6, 1)),
        Lot("L1", "A", 3, date(2026, 5, 1)),
        Lot("L3", "B", 9, date(2026, 5, 1)),
    ]
    orders = [Order("o1", "A", 4, date(2026, 4, 1)), Order("o2", "A", 10, date(2026, 4, 2))]
    alloc, rem = allocate(orders, lots)
    assert alloc == [("o1", [("L1", 3), ("L2", 1)]), ("o2", [("L2", 4)])]
    assert rem == {"L1": 0, "L2": 0, "L3": 9}
