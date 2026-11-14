import time
from collections import OrderedDict

_MISSING = object()


class TTLCache:
    def __init__(self, capacity, ttl, clock=time.monotonic):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if ttl <= 0:
            raise ValueError("ttl must be > 0")
        self.capacity = capacity
        self.ttl = ttl
        self._clock = clock
        self._data = OrderedDict()  # key -> (value, expires_at)

    def _alive(self, key, now):
        item = self._data.get(key, _MISSING)
        if item is _MISSING:
            return _MISSING
        if now >= item[1]:
            del self._data[key]
            return _MISSING
        return item

    def _purge(self, now):
        for k in [k for k, (_, exp) in self._data.items() if now >= exp]:
            del self._data[k]

    def put(self, key, value):
        now = self._clock()
        self._data[key] = (value, now + self.ttl)
        self._data.move_to_end(key)
        if len(self._data) > self.capacity:
            self._purge(now)
            while len(self._data) > self.capacity:
                self._data.popitem(last=False)

    def get(self, key, default=None):
        item = self._alive(key, self._clock())
        if item is _MISSING:
            return default
        self._data.move_to_end(key)
        return item[0]

    def delete(self, key):
        if self._alive(key, self._clock()) is _MISSING:
            return False
        del self._data[key]
        return True

    def __len__(self):
        self._purge(self._clock())
        return len(self._data)

    def __contains__(self, key):
        return self._alive(key, self._clock()) is not _MISSING
