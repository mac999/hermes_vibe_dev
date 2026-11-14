import pytest
from cache import TTLCache


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


def test_invalid_args(clock):
    with pytest.raises(ValueError):
        TTLCache(0, 1, clock)
    with pytest.raises(ValueError):
        TTLCache(1, 0, clock)
    with pytest.raises(ValueError):
        TTLCache(1, -1, clock)


def test_basic_put_get(clock):
    c = TTLCache(2, 10, clock)
    c.put("a", 1)
    assert c.get("a") == 1
    assert c.get("zz") is None
    assert c.get("zz", 5) == 5


def test_none_value_is_stored(clock):
    c = TTLCache(2, 10, clock)
    c.put("a", None)
    assert "a" in c
    assert c.get("a", "missing") is None
    assert len(c) == 1


def test_expiry_boundary(clock):
    c = TTLCache(2, 10, clock)
    c.put("a", 1)
    clock.t += 9.999
    assert c.get("a") == 1
    clock.t += 0.001
    assert c.get("a") is None
    assert "a" not in c
    assert len(c) == 0


def test_get_does_not_extend_ttl(clock):
    c = TTLCache(2, 10, clock)
    c.put("a", 1)
    clock.t += 6
    assert c.get("a") == 1
    clock.t += 5
    assert c.get("a") is None


def test_put_existing_resets_ttl(clock):
    c = TTLCache(2, 10, clock)
    c.put("a", 1)
    clock.t += 6
    c.put("a", 2)
    clock.t += 6
    assert c.get("a") == 2


def test_lru_eviction(clock):
    c = TTLCache(2, 100, clock)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")
    c.put("c", 3)
    assert "b" not in c
    assert c.get("a") == 1 and c.get("c") == 3


def test_contains_does_not_touch_recency(clock):
    c = TTLCache(2, 100, clock)
    c.put("a", 1)
    c.put("b", 2)
    assert "a" in c
    c.put("c", 3)
    assert "a" not in c
    assert "b" in c


def test_put_existing_moves_to_most_recent(clock):
    c = TTLCache(2, 100, clock)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    assert "b" not in c
    assert c.get("a") == 10


def test_expired_evicted_before_lru(clock):
    c = TTLCache(3, 10, clock)
    c.put("old", 0)
    clock.t += 5
    c.put("x", 1)
    c.put("y", 2)
    c.get("old")  # most recently used, but will expire first
    clock.t += 5  # "old" now expired
    c.put("z", 3)
    assert "x" in c and "y" in c and "z" in c
    assert len(c) == 3


def test_delete(clock):
    c = TTLCache(2, 10, clock)
    c.put("a", 1)
    assert c.delete("a") is True
    assert c.delete("a") is False
    c.put("b", 1)
    clock.t += 10
    assert c.delete("b") is False


def test_len_ignores_expired(clock):
    c = TTLCache(5, 10, clock)
    c.put("a", 1)
    clock.t += 5
    c.put("b", 2)
    assert len(c) == 2
    clock.t += 5
    assert len(c) == 1


def test_default_clock_works():
    c = TTLCache(1, 60)
    c.put("k", "v")
    assert c.get("k") == "v"
