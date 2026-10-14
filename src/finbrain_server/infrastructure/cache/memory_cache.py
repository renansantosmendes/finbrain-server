"""Thread-safe in-memory cache with time to live and LRU eviction."""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, TypeVar

from finbrain_server.application.ports import Cache

T = TypeVar("T")


class InMemoryTtlCache(Cache):
    """Cache kept in the memory of the process.

    Each entry expires after its own time to live; when the cache is full,
    the least recently used entry is dropped. Concurrent misses of the same
    key load the value only once: the other requests wait for it.

    On serverless platforms (Vercel) every instance has its own cache, so
    the API also sends ``Cache-Control`` headers for the CDN.

    Parameters
    ----------
    max_entries : int
        Maximum number of entries kept.
    clock : Callable[[], float]
        Monotonic clock in seconds (replaceable in tests).

    Example
    -------
    >>> cache = InMemoryTtlCache(max_entries=100)
    >>> cache.get_or_load("answer", 60, lambda: 42)
    42
    """

    def __init__(
        self,
        max_entries: int = 512,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}
        self._hits = 0
        self._misses = 0

    def get_or_load(
        self,
        key: str,
        ttl_seconds: float,
        loader: Callable[[], T],
    ) -> T:
        """Return the cached value of ``key`` or load and store it.

        Parameters
        ----------
        key : str
            Identifier of the value.
        ttl_seconds : float
            How long a loaded value stays valid.
        loader : Callable[[], T]
            Produces the value on a miss. Errors are not cached.

        Returns
        -------
        T
            Cached or freshly loaded value.
        """
        found, value = self._lookup(key)
        if found:
            return value
        with self._lock_for(key):
            found, value = self._lookup(key, count=False)
            if found:
                return value
            value = loader()
            with self._lock:
                self._entries[key] = (self._clock() + ttl_seconds, value)
                self._entries.move_to_end(key)
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)
            return value

    def stats(self) -> dict[str, int]:
        """Usage counters of the cache.

        Returns
        -------
        dict[str, int]
            ``entries``, ``max_entries``, ``hits`` and ``misses``.
        """
        with self._lock:
            return {
                "entries": len(self._entries),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
            }

    def clear(self) -> None:
        """Remove every entry and reset the counters."""
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0

    def _lookup(
        self,
        key: str,
        count: bool = True,
    ) -> tuple[bool, Any]:
        """Find a valid entry, dropping it when expired.

        Parameters
        ----------
        key : str
            Identifier of the value.
        count : bool
            Whether the lookup updates the hit and miss counters.

        Returns
        -------
        tuple[bool, Any]
            ``(True, value)`` on a hit, ``(False, None)`` otherwise.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry[0] > self._clock():
                self._entries.move_to_end(key)
                if count:
                    self._hits += 1
                return True, entry[1]
            if entry is not None:
                del self._entries[key]
            if count:
                self._misses += 1
            return False, None

    def _lock_for(self, key: str) -> threading.Lock:
        """Lock that serializes the loading of one key.

        Parameters
        ----------
        key : str
            Identifier of the value.

        Returns
        -------
        threading.Lock
            The same lock for every caller of the key.
        """
        with self._lock:
            if len(self._key_locks) > self._max_entries * 4:
                self._key_locks = {
                    name: lock
                    for name, lock in self._key_locks.items()
                    if lock.locked()
                }
            return self._key_locks.setdefault(key, threading.Lock())
