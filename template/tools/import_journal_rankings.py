#!/usr/bin/env python3
"""Import journal rankings from CSV into the PKB scholarly registry.

Usage:
    python tools/import_journal_rankings.py <csv_file> [--scheme LABEL] [--source-url URL]
    python tools/import_journal_rankings.py --list           # Show imported schemes
    python tools/import_journal_rankings.py --clear SCHEME   # Remove a scheme
    python tools/import_journal_rankings.py --validate <csv> # Dry-run validation only

CSV format (UTF-8, header required):
    scheme,edition,journal_name,issn,eissn,issn_l,level,category

    scheme    — CSSCI / PKU_CORE / AMI / CSCD / CUSTOM
    edition   — e.g. "2025-2026", "2023", "2022"
    journal_name — original name from the ranking authority
    issn      — print ISSN (XXXX-XXXX), may be empty
    eissn     — electronic ISSN, may be empty
    issn_l    — linking ISSN, may be empty
    level     — source / extended / core / authoritative / top / …
    category  — subject category (e.g. "新闻学与传播学")

Optional columns:
    source_label, source_url, verified_at

This tool does NOT ship real CSSCI / PKU Core / AMI / CSCD lists.
Users must obtain them from authorised sources.

Data is stored in .pkb_local/scholarly/rankings/journal_registry.sqlite3
This directory is protected by update_pkb.py and not committed to git.
"""

import sys
from pathlib import Path

# Ensure tools/ is on path so we can import scholarly
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from scholarly.journal_registry import JournalRegistry, normalise_issn, validate_issn, _normalise_name
from scholarly.models import JournalRanking


def cmd_import(args):
    """Import a CSV file into the registry."""
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    source_label = args.scheme or csv_path.stem
    source_url = args.source_url or ""

    print(f"Importing: {csv_path}")
    print(f"  Source label: {source_label}")
    print()

    registry = JournalRegistry()
    registry.conn.row_factory = None
    cur = registry.conn.cursor()

    # We'll use a cursor-based approach for accurate counting
    inserted = 0
    skipped_dup = 0
    skipped_invalid = 0
    errors = []

    import csv as csv_mod
    verified_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).strftime("%Y-%m-%d")

    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv_mod.DictReader(f)
        if reader.fieldnames is None:
            print("ERROR: CSV has no header row")
            sys.exit(1)

        # Check for required columns case-insensitively
        fieldnames_lower = [fn.lower().strip() for fn in reader.fieldnames]
        required = ["scheme", "journal_name"]
        missing = [r for r in required if r not in fieldnames_lower]
        if missing:
            print(f"ERROR: Missing required columns: {missing}")
            print(f"Found columns: {reader.fieldnames}")
            sys.exit(1)

        for row_idx, row in enumerate(reader, start=2):
            try:
                ranking = _row_to_ranking_obj(row, source_label, source_url, verified_at)
                if ranking is None:
                    skipped_invalid += 1
                    errors.append(f"Row {row_idx}: missing scheme or journal_name")
                    continue
            except Exception as e:
                skipped_invalid += 1
                errors.append(f"Row {row_idx}: parse error: {e}")
                continue

            try:
                cur.execute(
                    """INSERT INTO rankings
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
                inserted += 1
            except Exception as e:
                if "UNIQUE constraint" in str(e):
                    skipped_dup += 1
                else:
                    skipped_invalid += 1
                    errors.append(f"Row {row_idx}: DB error: {e}")

    registry.conn.commit()

    # Print report
    print(f"  Inserted:      {inserted}")
    print(f"  Duplicates:    {skipped_dup}")
    print(f"  Invalid/skip:  {skipped_invalid}")
    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for err in errors[:20]:
            print(f"    - {err}")
        if len(errors) > 20:
            print(f"    ... and {len(errors) - 20} more")
    print(f"\n  Total in DB:   {registry.count()}")
    registry.close()


def _row_to_ranking_obj(row, source_label, source_url, verified_at):
    """Convert CSV row dict to JournalRanking."""
    def _get(*keys):
        for k in keys:
            if k in row:
                return (row[k] or "").strip()
        for rk, rv in row.items():
            if rk.lower().strip() in [k.lower() for k in keys]:
                return (rv or "").strip()
        return ""

    scheme = _get("scheme")
    journal_name = _get("journal_name", "journal name")
    if not scheme or not journal_name:
        return None

    edition = _get("edition")
    issn_raw = _get("issn")
    eissn_raw = _get("eissn")
    issn_l_raw = _get("issn_l", "issn-l", "issn l")

    issn = normalise_issn(issn_raw) if issn_raw else ""
    eissn = normalise_issn(eissn_raw) if eissn_raw else ""
    issn_l = normalise_issn(issn_l_raw) if issn_l_raw else ""
    if not issn_l and issn:
        issn_l = issn

    normalized_name = _normalise_name(journal_name)
    level = _get("level")
    category = _get("category")

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
        source_label=source_label,
        source_url=source_url,
        verified_at=verified_at,
    )


def cmd_list(args):
    """List imported schemes and counts."""
    registry = JournalRegistry()
    schemes = registry.list_schemes()
    if not schemes:
        print("No rankings imported yet.")
        print("Use: python tools/import_journal_rankings.py <file.csv>")
        registry.close()
        return

    print(f"{'Scheme':<16} {'Edition':<16} {'Count':>8}")
    print("-" * 42)
    for scheme, edition in schemes:
        count = len(registry.query_by_scheme(scheme, edition))
        print(f"{scheme:<16} {edition:<16} {count:>8}")
    print("-" * 42)
    print(f"{'TOTAL':<33} {registry.count():>8}")
    registry.close()


def cmd_clear(args):
    """Clear a specific scheme."""
    scheme = args.scheme.upper()
    registry = JournalRegistry()
    count = len(registry.query_by_scheme(scheme))
    if count == 0:
        print(f"No entries for scheme '{scheme}'")
        registry.close()
        return

    print(f"Removing {count} entries for scheme '{scheme}'...")
    registry.conn.execute("DELETE FROM rankings WHERE scheme=?", (scheme,))
    registry.conn.commit()
    print("Done.")
    registry.close()


def cmd_validate(args):
    """Validate a CSV without importing."""
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    import csv as csv_mod
    ok = 0
    invalid = 0
    errors = []

    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv_mod.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):
            scheme = row.get("scheme", "").strip()
            journal_name = row.get("journal_name", row.get("journal name", "")).strip()
            issn_raw = row.get("issn", "").strip()

            row_ok = True
            if not scheme:
                errors.append(f"Row {row_idx}: missing scheme")
                row_ok = False
            if not journal_name:
                errors.append(f"Row {row_idx}: missing journal_name")
                row_ok = False
            if issn_raw:
                n, valid = validate_issn(issn_raw)
                if not valid:
                    errors.append(f"Row {row_idx}: invalid ISSN '{issn_raw}' (got '{n}')")
                    row_ok = False

            if row_ok:
                ok += 1
            else:
                invalid += 1

    print(f"Validation complete:")
    print(f"  Valid rows:    {ok}")
    print(f"  Invalid rows:  {invalid}")
    if errors:
        print(f"\n  Issues ({len(errors)}):")
        for err in errors[:30]:
            print(f"    - {err}")
        if len(errors) > 30:
            print(f"    ... and {len(errors) - 30} more")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="PKB Journal Rankings Importer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Commands")

    # import
    p_import = sub.add_parser("import", help="Import a CSV file")
    p_import.add_argument("csv", help="Path to CSV file")
    p_import.add_argument("--scheme", default="", help="Override scheme label")
    p_import.add_argument("--source-url", default="", help="Data source URL")

    # list
    sub.add_parser("list", help="List imported schemes and counts")

    # clear
    p_clear = sub.add_parser("clear", help="Remove a scheme's entries")
    p_clear.add_argument("scheme", help="Scheme to clear")

    # validate
    p_validate = sub.add_parser("validate", help="Validate CSV without importing")
    p_validate.add_argument("csv", help="Path to CSV file")

    # Legacy positional mode: first arg is a CSV file path
    args, unknown = parser.parse_known_args()

    if args.command is None and unknown:
        # Treat first unknown as CSV for legacy Mode B compat
        csv_file = unknown[0]
        args.csv = csv_file
        args.command = "import"

    if args.command == "import":
        cmd_import(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "clear":
        cmd_clear(args)
    elif args.command == "validate":
        cmd_validate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
