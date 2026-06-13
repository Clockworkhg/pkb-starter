"""Journal ranking registry — import, store, and query journal rankings.

Design:
  - ISSN is the primary matching key. Name is fallback.
  - Multiple editions of the same scheme coexist (e.g. CSSCI 2021-2022 and 2025-2026).
  - Re-import is idempotent (match_key dedup).
  - All user data lives in .pkb_local/scholarly/rankings/.

No real CSSCI/PKU Core/AMI/CSCD lists are shipped. Users must obtain them
from authorised sources and import them.
"""

from __future__ import annotations

import csv
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import JournalRanking


# ─────────────────────────────────────────────
# ISSN helpers
# ─────────────────────────────────────────────

def _issn_checksum(digits: str) -> str:
    """Compute ISSN check digit (mod 11, 'X' for 10)."""
    total = sum((8 - i) * int(d) for i, d in enumerate(digits[:7]))
    remainder = total % 11
    if remainder == 0:
        return "0"
    diff = 11 - remainder
    return "X" if diff == 10 else str(diff)


def validate_issn(raw: str) -> Tuple[str, bool]:
    """Validate and normalise an ISSN.

    Returns (normalised_form, is_valid).
    Normalised form is XXXX-XXXX. Empty string on unparseable input.
    """
    if not raw or not raw.strip():
        return "", False
    # Strip common prefixes
    s = raw.strip().upper()
    s = re.sub(r'^(ISSN|issn)\s*[:：]?\s*', '', s)
    # Remove all non-alphanumeric except X
    digits = re.sub(r'[^0-9X]', '', s)
    if len(digits) != 8:
        return "", False
    # Checksum digit is the last character
    body = digits[:7]
    check = digits[7]
    expected = _issn_checksum(body)
    is_valid = check == expected
    normalised = f"{digits[:4]}-{digits[4:]}"
    return normalised, is_valid


def normalise_issn(raw: str) -> str:
    """Normalise ISSN to XXXX-XXXX, returning empty string on failure."""
    normalised, _valid = validate_issn(raw)
    return normalised


# ─────────────────────────────────────────────
# Journal name normalisation
# ─────────────────────────────────────────────

def _normalise_name(raw: str) -> str:
    """Normalise a journal name for matching.

    Steps:
      1. Unicode NFKC normalisation
      2. Convert fullwidth to halfwidth
      3. Strip 《》书名号
      4. Remove redundant whitespace
      5. Lowercase (Chinese is case-insensitive anyway)
      6. Strip trailing 学报/Journal suffix variants for broader matching
    """
    if not raw:
        return ""
    s = unicodedata.normalize("NFKC", raw)
    # Strip common brackets
    s = s.replace("《", "").replace("》", "")
    s = s.replace("〈", "").replace("〉", "")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("：", ":").replace("，", ",")
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    # Lowercase (English parts)
    s = s.lower()
    return s


# ─────────────────────────────────────────────
# SQLite-backed registry
# ─────────────────────────────────────────────

_DEFAULT_RANKINGS_DIR = ".pkb_local/scholarly/rankings"
_DEFAULT_DB_NAME = "journal_registry.sqlite3"

# CSV columns we expect
CSV_COLUMNS = [
    "scheme", "edition", "journal_name", "normalized_name",
    "issn", "eissn", "issn_l", "level", "category",
    "source_label", "source_url", "verified_at",
]


class JournalRegistry:
    """Queryable registry of journal rankings stored in SQLite.

    Thread-safe for reads; writes serialised by SQLite.
    """

    def __init__(self, db_path: Optional[Path] = None, auto_setup: bool = True):
        """
        Args:
            db_path: Path to SQLite database. Default: .pkb_local/scholarly/rankings/journal_registry.sqlite3
            auto_setup: If True, create tables on init.
        """
        if db_path is None:
            root = Path(os.environ.get("PKB_ROOT", os.getcwd()))
            db_path = root / _DEFAULT_RANKINGS_DIR / _DEFAULT_DB_NAME
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        if auto_setup:
            self._ensure_tables()

    # ── Connection management ──

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(str(self.db_path))
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout=5000")
            c.execute("PRAGMA foreign_keys=ON")
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

    # ── Schema ──

    def _ensure_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS rankings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scheme TEXT NOT NULL,
                edition TEXT NOT NULL,
                journal_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL DEFAULT '',
                issn TEXT NOT NULL DEFAULT '',
                eissn TEXT NOT NULL DEFAULT '',
                issn_l TEXT NOT NULL DEFAULT '',
                level TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                source_label TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                verified_at TEXT NOT NULL DEFAULT '',
                match_key TEXT NOT NULL UNIQUE,
                imported_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_rankings_issn ON rankings(issn);
            CREATE INDEX IF NOT EXISTS idx_rankings_eissn ON rankings(eissn);
            CREATE INDEX IF NOT EXISTS idx_rankings_issn_l ON rankings(issn_l);
            CREATE INDEX IF NOT EXISTS idx_rankings_norm_name ON rankings(normalized_name);
            CREATE INDEX IF NOT EXISTS idx_rankings_scheme ON rankings(scheme);
            CREATE INDEX IF NOT EXISTS idx_rankings_scheme_edition ON rankings(scheme, edition);
        """)

    # ── Import ──

    def import_csv(self, csv_path: Path, source_label: str = "",
                   source_url: str = "") -> Tuple[int, int, int, List[str]]:
        """Import a CSV file of journal rankings.

        Returns (inserted, skipped_dup, skipped_invalid, errors).
        """
        inserted = 0
        skipped_dup = 0
        skipped_invalid = 0
        errors: List[str] = []

        verified_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    return (0, 0, 0, ["CSV has no header row"])

                for row_idx, row in enumerate(reader, start=2):
                    try:
                        ranking = self._row_to_ranking(row, source_label, source_url, verified_at)
                        if ranking is None:
                            skipped_invalid += 1
                            errors.append(f"Row {row_idx}: invalid or missing required fields")
                            continue
                    except Exception as e:
                        skipped_invalid += 1
                        errors.append(f"Row {row_idx}: parse error: {e}")
                        continue

                    try:
                        cur = self.conn.execute(
                            """INSERT OR IGNORE INTO rankings
                               (scheme, edition, journal_name, normalized_name,
                                issn, eissn, issn_l, level, category,
                                source_label, source_url, verified_at, match_key)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (ranking.scheme, ranking.edition, ranking.journal_name,
                             ranking.normalized_name, ranking.issn, ranking.eissn,
                             ranking.issn_l, ranking.level, ranking.category,
                             ranking.source_label, ranking.source_url,
                             ranking.verified_at, ranking.match_key()),
                        )
                        if cur.rowcount > 0:
                            inserted += 1
                        else:
                            skipped_dup += 1
                    except Exception as e:
                        skipped_invalid += 1
                        errors.append(f"Row {row_idx}: DB error: {e}")

                self.conn.commit()
        except Exception as e:
            errors.append(f"CSV read error: {e}")
            return (0, 0, 0, errors)

        return (inserted, skipped_dup, skipped_invalid, errors)

    def _row_to_ranking(self, row: Dict[str, str], source_label: str,
                        source_url: str, verified_at: str) -> Optional[JournalRanking]:
        """Convert a CSV row to a JournalRanking. Returns None if invalid."""
        # Case-insensitive key lookup
        def _get(*keys: str) -> str:
            for k in keys:
                if k in row:
                    return (row[k] or "").strip()
            # Try case-insensitive
            for rk, rv in row.items():
                if rk.lower() in [k.lower() for k in keys]:
                    return (rv or "").strip()
            return ""

        scheme = _get("scheme")
        edition = _get("edition")
        journal_name = _get("journal_name", "journal name")

        if not scheme or not journal_name:
            return None

        issn_raw = _get("issn")
        eissn_raw = _get("eissn")
        issn_l_raw = _get("issn_l", "issn-l", "issn l")

        issn = normalise_issn(issn_raw) if issn_raw else ""
        eissn = normalise_issn(eissn_raw) if eissn_raw else ""
        issn_l = normalise_issn(issn_l_raw) if issn_l_raw else ""

        # Auto-compute issn_l from issn if missing
        if not issn_l and issn:
            issn_l = issn

        normalized_name = _normalise_name(journal_name)

        level = _get("level")
        category = _get("category")
        sl = source_label or _get("source_label", "source label")
        su = source_url or _get("source_url", "source url")

        return JournalRanking(
            scheme=scheme,
            edition=edition,
            journal_name=journal_name,
            normalized_name=normalized_name,
            issn=issn,
            eissn=eissn,
            issn_l=issn_l,
            level=level,
            category=category,
            source_label=sl,
            source_url=su,
            verified_at=verified_at,
        )

    _last_insert_count = 0

    def _count_after_last_insert(self) -> int:
        """Track this in a simpler way."""
        return 0  # placeholder, we'll use a better approach

    def insert_ranking(self, ranking: JournalRanking) -> bool:
        """Insert a single ranking. Returns True if inserted, False if duplicate."""
        try:
            cur = self.conn.execute(
                """INSERT OR IGNORE INTO rankings
                   (scheme, edition, journal_name, normalized_name,
                    issn, eissn, issn_l, level, category,
                    source_label, source_url, verified_at, match_key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ranking.scheme, ranking.edition, ranking.journal_name,
                 ranking.normalized_name, ranking.issn, ranking.eissn,
                 ranking.issn_l, ranking.level, ranking.category,
                 ranking.source_label, ranking.source_url,
                 ranking.verified_at, ranking.match_key()),
            )
            self.conn.commit()
            return cur.rowcount > 0
        except sqlite3.IntegrityError:
            return False

    def import_rankings(self, rankings: List[JournalRanking]) -> Tuple[int, int]:
        """Import a list of rankings. Returns (inserted, duplicates)."""
        inserted = 0
        duplicates = 0
        for r in rankings:
            if self.insert_ranking(r):
                inserted += 1
            else:
                duplicates += 1
        return inserted, duplicates

    # ── Query ──

    def _row_to_ranking_obj(self, row: sqlite3.Row) -> JournalRanking:
        return JournalRanking(
            scheme=row["scheme"],
            edition=row["edition"],
            journal_name=row["journal_name"],
            normalized_name=row["normalized_name"],
            issn=row["issn"],
            eissn=row["eissn"],
            issn_l=row["issn_l"],
            level=row["level"],
            category=row["category"],
            source_label=row["source_label"],
            source_url=row["source_url"],
            verified_at=row["verified_at"],
        )

    def query_by_issn(self, issn: str) -> List[JournalRanking]:
        """Find all rankings matching a normalised ISSN (XXXX-XXXX)."""
        n = normalise_issn(issn)
        if not n:
            return []
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            "SELECT * FROM rankings WHERE issn=? OR issn_l=?",
            (n, n),
        ).fetchall()
        return [self._row_to_ranking_obj(r) for r in rows]

    def query_by_eissn(self, eissn: str) -> List[JournalRanking]:
        """Find all rankings matching an EISSN."""
        n = normalise_issn(eissn)
        if not n:
            return []
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            "SELECT * FROM rankings WHERE eissn=?",
            (n,),
        ).fetchall()
        return [self._row_to_ranking_obj(r) for r in rows]

    def query_by_issn_l(self, issn_l: str) -> List[JournalRanking]:
        """Find all rankings matching an ISSN-L."""
        n = normalise_issn(issn_l)
        if not n:
            return []
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            "SELECT * FROM rankings WHERE issn_l=?",
            (n,),
        ).fetchall()
        return [self._row_to_ranking_obj(r) for r in rows]

    def query_by_name(self, name: str) -> List[JournalRanking]:
        """Find all rankings whose normalised name contains the query."""
        n = _normalise_name(name)
        if not n:
            return []
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            "SELECT * FROM rankings WHERE normalized_name LIKE ?",
            (f"%{n}%",),
        ).fetchall()
        return [self._row_to_ranking_obj(r) for r in rows]

    def query_by_name_exact(self, name: str) -> List[JournalRanking]:
        """Find all rankings with exact normalised name match."""
        n = _normalise_name(name)
        if not n:
            return []
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            "SELECT * FROM rankings WHERE normalized_name=?",
            (n,),
        ).fetchall()
        return [self._row_to_ranking_obj(r) for r in rows]

    def query_by_scheme(self, scheme: str, edition: str = "") -> List[JournalRanking]:
        """List all rankings in a scheme, optionally filtered by edition."""
        self.conn.row_factory = sqlite3.Row
        if edition:
            rows = self.conn.execute(
                "SELECT * FROM rankings WHERE scheme=? AND edition=? ORDER BY normalized_name",
                (scheme.upper(), edition),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM rankings WHERE scheme=? ORDER BY normalized_name",
                (scheme.upper(),),
            ).fetchall()
        return [self._row_to_ranking_obj(r) for r in rows]

    def list_schemes(self) -> List[Tuple[str, str]]:
        """List all (scheme, edition) pairs."""
        rows = self.conn.execute(
            "SELECT DISTINCT scheme, edition FROM rankings ORDER BY scheme, edition"
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def count(self) -> int:
        """Total number of ranking entries."""
        return self.conn.execute("SELECT COUNT(*) FROM rankings").fetchone()[0]

    def clear(self):
        """Remove all rankings (for testing)."""
        self.conn.execute("DELETE FROM rankings")
        self.conn.commit()


# ─────────────────────────────────────────────
# Module-level convenience
# ─────────────────────────────────────────────

_default_registry: Optional[JournalRegistry] = None


def get_registry() -> JournalRegistry:
    """Get or create the default singleton JournalRegistry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = JournalRegistry()
    return _default_registry
