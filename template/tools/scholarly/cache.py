"""SQLite cache for scholarly metadata lookups.

Design:
  - Python stdlib sqlite3 only — no external dependencies.
  - namespace + cache_key → payload (JSON blob) + expiry.
  - Static metadata TTL: 30 days. Dynamic metrics TTL: 7 days.
  - TTL overridable per-call or via config.
  - Time is injectable for testing (clock parameter).
  - Transactions for writes; WAL mode; busy timeout.
  - Never caches API keys, email, or credentials.

Default path: .pkb_local/scholarly/cache.sqlite3
"""

from __future__ import annotations

import json
import os
import sqlite3
import time as _time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple


# ─────────────────────────────────────────────
# TTL defaults (seconds)
# ─────────────────────────────────────────────

TTL_STATIC = 30 * 24 * 3600     # 30 days — bibliographic metadata
TTL_DYNAMIC = 7 * 24 * 3600     # 7 days — citation counts, metrics
TTL_SHORT = 24 * 3600           # 1 day — journal list lookups

# Namespaces
NS_CROSSREF = "crossref"
NS_OPENALEX_WORK = "openalex_work"
NS_OPENALEX_SOURCE = "openalex_source"
NS_OPENALEX_METRICS = "openalex_metrics"


# ─────────────────────────────────────────────
# SQLite cache
# ─────────────────────────────────────────────

class ScholarlyCache:
    """SQLite-backed cache for scholarly metadata.

    Usage:
        cache = ScholarlyCache()
        cache.set("crossref", "10.1234/foo", {"title": "..."}, ttl=TTL_STATIC)
        hit, payload = cache.get("crossref", "10.1234/foo")
    """

    _DEFAULT_DB_PATH = ".pkb_local/scholarly/cache.sqlite3"

    def __init__(self, db_path: Optional[Path] = None,
                 clock: Optional[Callable[[], float]] = None):
        """
        Args:
            db_path: Path to SQLite file. Default: .pkb_local/scholarly/cache.sqlite3
            clock: Time function for testing injection. Default: time.time()
        """
        if db_path is None:
            root = Path(os.environ.get("PKB_ROOT", os.getcwd()))
            db_path = root / self._DEFAULT_DB_PATH
        self.db_path = Path(db_path)
        self._clock = clock or _time.time
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(str(self.db_path))
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout=5000")
            self._conn = c
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _ensure_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                UNIQUE(namespace, cache_key)
            );
            CREATE INDEX IF NOT EXISTS idx_cache_lookup ON cache_entries(namespace, cache_key);
            CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at);
        """)

    def _now_iso(self) -> str:
        return datetime.fromtimestamp(self._clock(), tz=timezone.utc).isoformat()

    # ── Core CRUD ──

    def get(self, namespace: str, cache_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Look up a cached entry. Returns (hit, payload_dict).

        hit is False if not found or expired.
        """
        now = self._now_iso()
        row = self.conn.execute(
            "SELECT payload_json, expires_at FROM cache_entries "
            "WHERE namespace=? AND cache_key=?",
            (namespace, cache_key),
        ).fetchone()

        if row is None:
            return False, None

        payload_json, expires_at = row
        if expires_at < now:
            # Expired — remove it lazily
            self.conn.execute(
                "DELETE FROM cache_entries WHERE namespace=? AND cache_key=?",
                (namespace, cache_key),
            )
            self.conn.commit()
            return False, None

        try:
            payload = json.loads(payload_json)
            return True, payload
        except json.JSONDecodeError:
            return False, None

    def set(self, namespace: str, cache_key: str, payload: Dict[str, Any],
            ttl: Optional[int] = None) -> None:
        """Store a cache entry. Uses INSERT OR REPLACE for idempotency."""
        if ttl is None:
            ttl = TTL_STATIC

        now_ts = self._clock()
        created_at = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()
        expires_at = datetime.fromtimestamp(now_ts + ttl, tz=timezone.utc).isoformat()
        payload_json = json.dumps(payload, ensure_ascii=False)

        self.conn.execute(
            """INSERT OR REPLACE INTO cache_entries
               (namespace, cache_key, payload_json, created_at, expires_at)
               VALUES (?,?,?,?,?)""",
            (namespace, cache_key, payload_json, created_at, expires_at),
        )
        self.conn.commit()

    def delete(self, namespace: str, cache_key: str) -> bool:
        """Delete a cache entry. Returns True if something was deleted."""
        cur = self.conn.execute(
            "DELETE FROM cache_entries WHERE namespace=? AND cache_key=?",
            (namespace, cache_key),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def purge_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        now = self._now_iso()
        cur = self.conn.execute(
            "DELETE FROM cache_entries WHERE expires_at < ?",
            (now,),
        )
        self.conn.commit()
        return cur.rowcount

    def clear_namespace(self, namespace: str) -> int:
        """Remove all entries in a namespace. Returns count."""
        cur = self.conn.execute(
            "DELETE FROM cache_entries WHERE namespace=?",
            (namespace,),
        )
        self.conn.commit()
        return cur.rowcount

    def count(self, namespace: Optional[str] = None) -> int:
        """Count entries, optionally filtered by namespace."""
        if namespace:
            return self.conn.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE namespace=?",
                (namespace,),
            ).fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]

    # ── Convenience ──

    def has(self, namespace: str, cache_key: str) -> bool:
        """Check if a non-expired entry exists."""
        hit, _ = self.get(namespace, cache_key)
        return hit

    def get_or_set(self, namespace: str, cache_key: str,
                   factory: Callable[[], Tuple[Dict[str, Any], int]]) -> Tuple[bool, Dict[str, Any]]:
        """Get cached value, or compute+store via factory if missing/expired.

        factory returns (payload_dict, ttl_seconds).
        Returns (was_cache_hit, payload_dict).
        """
        hit, payload = self.get(namespace, cache_key)
        if hit and payload is not None:
            return True, payload
        payload, ttl = factory()
        self.set(namespace, cache_key, payload, ttl=ttl)
        return False, payload


# ─────────────────────────────────────────────
# In-memory cache for testing
# ─────────────────────────────────────────────

class MemoryCache:
    """In-memory cache for unit tests. Same interface as ScholarlyCache."""

    def __init__(self, clock: Optional[Callable[[], float]] = None):
        self._store: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._clock = clock or _time.time

    def get(self, namespace: str, cache_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        full_key = f"{namespace}:{cache_key}"
        entry = self._store.get(full_key)
        if entry is None:
            return False, None
        payload, expires_ts = entry
        if self._clock() > expires_ts:
            del self._store[full_key]
            return False, None
        return True, payload

    def set(self, namespace: str, cache_key: str, payload: Dict[str, Any],
            ttl: Optional[int] = None) -> None:
        if ttl is None:
            ttl = TTL_STATIC
        full_key = f"{namespace}:{cache_key}"
        expires_ts = self._clock() + ttl
        self._store[full_key] = (payload, expires_ts)

    def delete(self, namespace: str, cache_key: str) -> bool:
        full_key = f"{namespace}:{cache_key}"
        if full_key in self._store:
            del self._store[full_key]
            return True
        return False

    def purge_expired(self) -> int:
        now = self._clock()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
        return len(expired)

    def clear_namespace(self, namespace: str) -> int:
        prefix = f"{namespace}:"
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            del self._store[k]
        return len(keys)

    def count(self, namespace: Optional[str] = None) -> int:
        if namespace:
            prefix = f"{namespace}:"
            return sum(1 for k in self._store if k.startswith(prefix))
        return len(self._store)

    def has(self, namespace: str, cache_key: str) -> bool:
        hit, _ = self.get(namespace, cache_key)
        return hit

    @property
    def conn(self):
        """Compat shim for tests."""
        return None

    def close(self):
        self._store.clear()
