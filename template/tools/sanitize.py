#!/usr/bin/env python3
"""PKB Privacy Sanitizer.

Scans files for sensitive patterns and optionally redacts them.

Usage:
    python tools/sanitize.py <file_or_directory>
    python tools/sanitize.py <file_or_directory> --fix   # auto-redact
    python tools/sanitize.py <file_or_directory> --json  # machine-readable output
"""

import os
import re
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# ── Detection Patterns ──────────────────────────────────────────

CRITICAL_PATTERNS = [
    # API Keys & Tokens
    (re.compile(r'(?:api[_-]?key|apikey)\s*[:=]\s*["\']?\w{20,}["\']?', re.IGNORECASE), "api_key"),
    (re.compile(r'(?:access[_-]?token|auth[_-]?token)\s*[:=]\s*["\']?[\w\-_.]{20,}["\']?', re.IGNORECASE), "token"),
    (re.compile(r'(?:secret|password|passwd)\s*[:=]\s*["\'][^"\']+["\']', re.IGNORECASE), "credential"),

    # Private Keys
    (re.compile(r'-----BEGIN (?:RSA|OPENSSH|EC|PGP) PRIVATE KEY-----'), "private_key"),

    # JWT Tokens
    (re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'), "jwt"),

    # Email addresses
    (re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'), "email"),
]

WARNING_PATTERNS = [
    # Potential Chinese ID numbers (18 digits)
    (re.compile(r'\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b'), "cn_id"),

    # Phone numbers (Chinese mobile)
    (re.compile(r'\b1[3-9]\d{9}\b'), "phone_cn"),

    # Credit card patterns (13-19 digits with dashes)
    (re.compile(r'\b(?:\d[ -]*?){13,19}\b'), "possible_cc"),
]

# Filenames that should never be committed
SENSITIVE_FILENAMES = [
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials.json", "serviceAccount.json", "service-account.json",
    "id_rsa", "id_rsa.pub", "id_ecdsa", "id_ecdsa.pub",
    "*.pem", "*.p12", "*.pfx", "*.key", "*.keystore", "*.jks", "*.ppk",
]


def scan_file(filepath: Path) -> list[dict]:
    """Scan a single file for sensitive patterns. Returns list of findings."""
    findings = []

    # Check filename
    for pattern in SENSITIVE_FILENAMES:
        if filepath.match(pattern):
            findings.append({
                "level": "critical",
                "type": "sensitive_filename",
                "file": str(filepath),
                "line": 0,
                "match": filepath.name,
            })
            return findings  # Don't scan content of known sensitive files

    # Skip binary files
    text_extensions = {'.md', '.txt', '.py', '.js', '.ts', '.json', '.yaml', '.yml',
                       '.html', '.css', '.csv', '.xml', '.toml', '.ini', '.cfg',
                       '.sh', '.ps1', '.bat', '.env'}
    if filepath.suffix.lower() not in text_extensions:
        return findings

    try:
        content = filepath.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return findings

    for line_no, line in enumerate(content.split('\n'), 1):
        # Critical patterns
        for pattern, ptype in CRITICAL_PATTERNS:
            for match in pattern.finditer(line):
                findings.append({
                    "level": "critical",
                    "type": ptype,
                    "file": str(filepath),
                    "line": line_no,
                    "match": match.group()[:80],
                })

        # Warning patterns
        for pattern, ptype in WARNING_PATTERNS:
            for match in pattern.finditer(line):
                findings.append({
                    "level": "warning",
                    "type": ptype,
                    "file": str(filepath),
                    "line": line_no,
                    "match": match.group()[:40],
                })

    return findings


def scan_directory(path: Path) -> dict:
    """Recursively scan a directory. Returns {filepath: [findings]}."""
    results = {}
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.obsidian', '.trash'}

    for root, dirs, files in os.walk(path):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

        for fname in files:
            fpath = Path(root) / fname
            findings = scan_file(fpath)
            if findings:
                results[str(fpath)] = findings

    return results


def redact_file(filepath: Path, findings: list[dict]) -> Path:
    """Create a redacted copy of the file. Returns path to redacted copy."""
    redacted_path = filepath.with_suffix(filepath.suffix + '.redacted')

    try:
        content = filepath.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return None

    # Group findings by line for efficient replacement
    for f in sorted(findings, key=lambda x: -x['line']):  # Process from bottom up
        lines = content.split('\n')
        line_idx = f['line'] - 1
        if 0 <= line_idx < len(lines):
            ptype = f['type']
            replacement = f"[REDACTED_{ptype}]"
            lines[line_idx] = lines[line_idx].replace(f['match'], replacement)
        content = '\n'.join(lines)

    redacted_path.write_text(content, encoding='utf-8')
    return redacted_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = Path(sys.argv[1])
    auto_fix = "--fix" in sys.argv
    json_output = "--json" in sys.argv

    if not target.exists():
        print(f"[ERROR] Path not found: {target}")
        sys.exit(1)

    # Scan
    if target.is_dir():
        results = scan_directory(target)
    else:
        findings = scan_file(target)
        results = {str(target): findings} if findings else {}

    # Count
    total_files_scanned = sum(1 for _ in _walk_text_files(target))
    total_findings = sum(len(v) for v in results.values())
    critical = sum(1 for v in results.values() for f in v if f['level'] == 'critical')
    warnings = sum(1 for v in results.values() for f in v if f['level'] == 'warning')

    if json_output:
        report = {
            "scan_target": str(target),
            "files_scanned": total_files_scanned,
            "files_with_findings": len(results),
            "total_findings": total_findings,
            "critical": critical,
            "warnings": warnings,
            "findings": {k: v for k, v in results.items()},
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if critical == 0 else 1

    # Human-readable report
    print("=" * 60)
    print("  PKB Sanitize Scan Report")
    print("=" * 60)
    print(f"  Target: {target}")
    print(f"  Files scanned: {total_files_scanned}")
    print(f"  Files with findings: {len(results)}")
    print()

    if not results:
        print("  [OK] No sensitive patterns detected.")
        return 0

    for fpath, findings in sorted(results.items()):
        print(f"  {fpath}:")
        for f in sorted(findings, key=lambda x: x['line']):
            level = "[CRITICAL]" if f['level'] == 'critical' else "[WARN]"
            print(f"    {level} L{f['line']}: [{f['type']}] {f['match'][:60]}")

    print()
    print(f"  Critical: {critical} | Warnings: {warnings}")

    if auto_fix and critical > 0:
        print()
        print("  Auto-redacting critical findings...")
        for fpath, findings in results.items():
            critical_findings = [f for f in findings if f['level'] == 'critical']
            if critical_findings:
                redacted = redact_file(Path(fpath), critical_findings)
                if redacted:
                    print(f"    {fpath} → {redacted}")

    return 0 if critical == 0 else 1


def _walk_text_files(path: Path):
    """Count text files recursively."""
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.obsidian', '.trash'}
    text_extensions = {'.md', '.txt', '.py', '.js', '.ts', '.json', '.yaml', '.yml',
                       '.html', '.css', '.csv', '.xml', '.toml', '.ini', '.cfg',
                       '.sh', '.ps1', '.bat'}
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        for fname in files:
            if Path(fname).suffix.lower() in text_extensions:
                yield Path(root) / fname


if __name__ == "__main__":
    sys.exit(main())
