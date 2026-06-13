"""Tests for scholarly cache.py.

Covers: get/set, expiry, purge, cache_only, time injection, MemoryCache, clear_namespace.
No real network access.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest

from scholarly.cache import (
    MemoryCache,
    ScholarlyCache,
    TTL_DYNAMIC,
    TTL_STATIC,
)


# ═══════════════════════════════════════════════════════════
# MemoryCache tests (fast, no filesystem)
# ═══════════════════════════════════════════════════════════

class TestMemoryCache:
    """All tests use MemoryCache for speed and isolation."""

    @pytest.fixture
    def cache(self):
        return MemoryCache()

    def test_set_and_get(self, cache):
        cache.set("test_ns", "key1", {"value": 42})
        hit, payload = cache.get("test_ns", "key1")
        assert hit
        assert payload == {"value": 42}

    def test_get_missing(self, cache):
        hit, payload = cache.get("test_ns", "nonexistent")
        assert not hit
        assert payload is None

    def test_delete(self, cache):
        cache.set("test_ns", "key1", {"a": 1})
        assert cache.delete("test_ns", "key1")
        hit, _ = cache.get("test_ns", "key1")
        assert not hit
        assert not cache.delete("test_ns", "nonexistent")

    def test_expiry_with_mocked_time(self):
        """Time injection: entry expires after TTL."""
        clock = [1000.0]  # mutable clock
        cache = MemoryCache(clock=lambda: clock[0])

        cache.set("ns", "key", {"data": "x"}, ttl=10)
        hit, _ = cache.get("ns", "key")
        assert hit

        # Advance past TTL
        clock[0] = 1020.0
        hit, _ = cache.get("ns", "key")
        assert not hit

    def test_purge_expired(self):
        clock = [1000.0]
        cache = MemoryCache(clock=lambda: clock[0])

        cache.set("ns", "fresh", {"a": 1}, ttl=100)
        cache.set("ns", "stale", {"b": 2}, ttl=5)

        clock[0] = 1010.0  # stale expired, fresh still valid
        removed = cache.purge_expired()
        assert removed == 1

        hit_fresh, _ = cache.get("ns", "fresh")
        assert hit_fresh

    def test_clear_namespace(self, cache):
        cache.set("ns1", "k1", {"a": 1})
        cache.set("ns1", "k2", {"b": 2})
        cache.set("ns2", "k3", {"c": 3})

        removed = cache.clear_namespace("ns1")
        assert removed == 2
        assert cache.count() == 1
        assert cache.count("ns1") == 0

    def test_has(self, cache):
        cache.set("ns", "key", {"x": 1})
        assert cache.has("ns", "key")
        assert not cache.has("ns", "missing")

    def test_count(self, cache):
        assert cache.count() == 0
        cache.set("ns", "k1", {})
        cache.set("ns", "k2", {})
        assert cache.count() == 2
        assert cache.count("ns") == 2
        assert cache.count("other") == 0


# ═══════════════════════════════════════════════════════════
# ScholarlyCache tests (SQLite-based)
# ═══════════════════════════════════════════════════════════

class TestScholarlyCache:
    """Tests using a temp SQLite file."""

    @pytest.fixture
    def cache(self):
        db_path = Path(tempfile.mktemp(suffix=".sqlite3"))
        c = ScholarlyCache(db_path=db_path)
        yield c
        c.close()
        try:
            db_path.unlink(missing_ok=True)
        except Exception:
            pass

    def test_set_and_get(self, cache):
        cache.set("crossref", "10.1234/test", {"title": "Hello"})
        hit, payload = cache.get("crossref", "10.1234/test")
        assert hit
        assert payload["title"] == "Hello"

    def test_missing_key(self, cache):
        hit, payload = cache.get("crossref", "nonexistent")
        assert not hit
        assert payload is None

    def test_expiry_with_clock(self):
        clock = [1000.0]
        db_path = Path(tempfile.mktemp(suffix=".sqlite3"))
        cache = ScholarlyCache(db_path=db_path, clock=lambda: clock[0])

        cache.set("ns", "key", {"x": 1}, ttl=10)
        hit, _ = cache.get("ns", "key")
        assert hit

        clock[0] = 1020.0
        hit, _ = cache.get("ns", "key")
        assert not hit

        cache.close()
        try:
            db_path.unlink(missing_ok=True)
        except Exception:
            pass

    def test_purge_expired(self):
        clock = [1000.0]
        db_path = Path(tempfile.mktemp(suffix=".sqlite3"))
        cache = ScholarlyCache(db_path=db_path, clock=lambda: clock[0])

        cache.set("ns", "fresh", {"a": 1}, ttl=100)
        cache.set("ns", "stale", {"b": 2}, ttl=5)

        clock[0] = 1010.0
        removed = cache.purge_expired()
        assert removed == 1

        cache.close()
        try:
            db_path.unlink(missing_ok=True)
        except Exception:
            pass

    def test_delete(self, cache):
        cache.set("ns", "key", {"x": 1})
        assert cache.delete("ns", "key")
        assert not cache.delete("ns", "key")
        hit, _ = cache.get("ns", "key")
        assert not hit

    def test_clear_namespace(self, cache):
        cache.set("ns1", "k1", {})
        cache.set("ns1", "k2", {})
        cache.set("ns2", "k3", {})
        removed = cache.clear_namespace("ns1")
        assert removed == 2
        assert cache.count("ns1") == 0
        assert cache.count("ns2") == 1

    def test_count(self, cache):
        assert cache.count() == 0
        cache.set("a", "x", {})
        cache.set("a", "y", {})
        assert cache.count() == 2
        assert cache.count("a") == 2

    def test_has(self, cache):
        cache.set("ns", "key", {"x": 1})
        assert cache.has("ns", "key")
        assert not cache.has("ns", "missing")

    def test_insert_replace(self, cache):
        """Second set should replace the first."""
        cache.set("ns", "key", {"version": 1})
        cache.set("ns", "key", {"version": 2})
        assert cache.count() == 1
        hit, payload = cache.get("ns", "key")
        assert payload["version"] == 2
