"""Journal matcher — match scholarly works to journal rankings.

Matching priority chain (each step tried in order, first success wins):
  1. DOI resolved ISSN exact match (doi_resolved_issn_exact)
  2. ISSN exact match (issn_exact)
  3. EISSN exact match (eissn_exact)
  4. ISSN-L exact match (issn_l_exact)
  5. Normalised name exact match (name_exact)
  6. Title + author + year fuzzy match (title_author_year_fuzzy)

Decision rules:
  - Identifier-based exact matches (1-4) auto-accept at confidence >= 0.92.
  - Name-based matches (5-6) never auto-accept regardless of score.
  - Name-exact (5) still takes priority over fuzzy (6).
  - ISSN/DOI matches are NEVER downgraded by name mismatch.
  - Rejected below 0.80 confidence.

Design:
  - Each MatchResult includes method, confidence, evidence, needs_review.
  - No heavy fuzzy-match deps — standard library only.
  - All match evidence is recorded, not just a score.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Set, Tuple

from .journal_registry import JournalRegistry, _normalise_name, normalise_issn
from .models import (
    JournalRanking,
    MatchMethod,
    MatchResult,
    ScholarlyRecord,
)


# ─────────────────────────────────────────────
# Normalisation helpers
# ─────────────────────────────────────────────

# Punctuation pattern: spaces, dashes, CJK punctuation marks, brackets, etc.
# Use explicit codepoints to avoid encoding corruption on Windows.
_PUNCT_RE = re.compile(
    r'[\s\-_\.,;:!?()\[\]{}/\\\|'
    r'—–'           # em dash, en dash
    r'（）'           # fullwidth parentheses （）
    r'、。'           # CJK comma 、 and period 。
    r'，．'           # fullwidth comma ， and period ．
    r'：；'           # fullwidth colon ： and semicolon ；
    r'！？'           # fullwidth exclamation ！ and question ？
    r'《》'           # CJK angle brackets 《》
    r'〈〉'           # CJK angle brackets 〈〉
    r'“”‘’'  # curly quotes
    r'【】'           # CJK square brackets 【】
    r'「」'           # CJK corner brackets 「」
    r']+'
)


def _collapse(s: str) -> str:
    """Aggressive collapse for fuzzy matching: NFKC → lowercase → strip punctuation."""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    s = _PUNCT_RE.sub('', s)
    return s


def _tokenize(s: str) -> Set[str]:
    """Tokenise into bigrams for fuzzy comparison."""
    collapsed = _collapse(s)
    bigrams: Set[str] = set()
    for i in range(len(collapsed) - 1):
        bigrams.add(collapsed[i:i + 2])
    return bigrams


def _bigram_similarity(a: str, b: str) -> float:
    """Dice coefficient over character bigrams."""
    if not a or not b:
        return 0.0
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return 0.0
    intersection = len(ta & tb)
    return 2.0 * intersection / (len(ta) + len(tb))


# ─────────────────────────────────────────────
# Matcher
# ─────────────────────────────────────────────

class JournalMatcher:
    """Match ScholarlyRecord against a JournalRegistry.

    Usage:
        registry = JournalRegistry()
        matcher = JournalMatcher(registry)
        result = matcher.match(record)
    """

    def __init__(self, registry: JournalRegistry):
        self.registry = registry

    def match(self, record: ScholarlyRecord) -> Optional[MatchResult]:
        """Run the priority chain and return the first successful MatchResult.

        Returns None if no match reaches the minimum confidence threshold (0.80).
        """
        # Priority 1: DOI → ISSN
        result = self._match_by_doi_issn(record)
        if result and result.is_auto_accepted():
            return result
        if result:
            # DOI-based match has high confidence but not auto-accept
            return result

        # Priority 2: ISSN exact
        result = self._match_by_issn(record)
        if result and result.is_auto_accepted():
            return result

        # Priority 3: EISSN exact
        result = self._match_by_eissn(record)
        if result and result.is_auto_accepted():
            return result

        # Priority 4: ISSN-L exact
        result = self._match_by_issn_l(record)
        if result and result.is_auto_accepted():
            return result

        # Priority 5: Normalised name exact
        # Name-exact matches are never auto-accepted (method-based rule),
        # but they still take priority over fuzzy matching.
        result = self._match_by_name(record)
        if result and not result.is_rejected():
            return result

        # Priority 6: Title + author + year fuzzy
        result = self._match_fuzzy(record)
        if result and not result.is_rejected():
            return result

        # No match above threshold
        return None

    # ── Individual match methods ──

    def _match_by_doi_issn(self, record: ScholarlyRecord) -> Optional[MatchResult]:
        """If we have ISSN from DOI metadata, do exact ISSN match."""
        if not record.issn and not record.issn_l:
            return None
        # Try each ISSN
        for issn in record.issn:
            n = normalise_issn(issn)
            if n:
                results = self.registry.query_by_issn(n)
                if results:
                    return MatchResult(
                        method=MatchMethod.DOI_RESOLVED_ISSN_EXACT,
                        confidence=1.0,
                        matched_id=results[0].match_key(),
                        evidence=[f"DOI resolved ISSN exact match: {n}"],
                        needs_review=False,
                    )
        # Try ISSN-L
        if record.issn_l:
            n = normalise_issn(record.issn_l)
            if n:
                results = self.registry.query_by_issn_l(n)
                if results:
                    return MatchResult(
                        method=MatchMethod.DOI_RESOLVED_ISSN_EXACT,
                        confidence=0.98,
                        matched_id=results[0].match_key(),
                        evidence=[f"DOI resolved ISSN-L exact match: {n}"],
                        needs_review=False,
                    )
        return None

    def _match_by_issn(self, record: ScholarlyRecord) -> Optional[MatchResult]:
        """Exact match on print ISSN."""
        if not record.issn:
            return None
        for issn in record.issn:
            n = normalise_issn(issn)
            if n:
                results = self.registry.query_by_issn(n)
                if results:
                    return MatchResult(
                        method=MatchMethod.ISSN_EXACT,
                        confidence=0.98,
                        matched_id=results[0].match_key(),
                        evidence=[f"ISSN exact match: {n}"],
                        needs_review=False,
                    )
        return None

    def _match_by_eissn(self, record: ScholarlyRecord) -> Optional[MatchResult]:
        """Exact match on electronic ISSN."""
        if record.journal_identity and record.journal_identity.eissn:
            n = normalise_issn(record.journal_identity.eissn)
            if n:
                results = self.registry.query_by_eissn(n)
                if results:
                    return MatchResult(
                        method=MatchMethod.EISSN_EXACT,
                        confidence=0.97,
                        matched_id=results[0].match_key(),
                        evidence=[f"EISSN exact match: {n}"],
                        needs_review=False,
                    )
        return None

    def _match_by_issn_l(self, record: ScholarlyRecord) -> Optional[MatchResult]:
        """Exact match on ISSN-L."""
        if not record.issn_l:
            return None
        n = normalise_issn(record.issn_l)
        if n:
            results = self.registry.query_by_issn_l(n)
            if results:
                return MatchResult(
                    method=MatchMethod.ISSN_L_EXACT,
                    confidence=0.96,
                    matched_id=results[0].match_key(),
                    evidence=[f"ISSN-L exact match: {n}"],
                    needs_review=False,
                )
        return None

    def _match_by_name(self, record: ScholarlyRecord) -> Optional[MatchResult]:
        """Exact normalised name match."""
        if not record.journal_name:
            return None
        n = _normalise_name(record.journal_name)
        if not n:
            return None
        results = self.registry.query_by_name_exact(n)
        if results:
            # Name-exact is high confidence but not perfect
            return MatchResult(
                method=MatchMethod.NAME_EXACT,
                confidence=0.92,
                matched_id=results[0].match_key(),
                evidence=[f"Normalised name exact match: {n}"],
                needs_review=True,
            )
        return None

    def _match_fuzzy(self, record: ScholarlyRecord) -> Optional[MatchResult]:
        """Fuzzy match on title + journal name.

        Uses bigram similarity on normalised names.
        """
        if not record.journal_name:
            return None

        norm_name = _normalise_name(record.journal_name)
        if not norm_name:
            return None

        # Search by name substring in registry — find close matches
        candidates = self.registry.query_by_name(norm_name[:30])
        if not candidates:
            # Try shorter prefix
            candidates = self.registry.query_by_name(norm_name[:15])

        if not candidates:
            return None

        best_score = 0.0
        best_match: Optional[JournalRanking] = None
        for c in candidates:
            score = _bigram_similarity(norm_name, c.normalized_name)
            if score > best_score:
                best_score = score
                best_match = c

        if best_match and best_score >= 0.80:
            evidence_parts = [f"Fuzzy name match: '{norm_name}' ≈ '{best_match.normalized_name}' (score={best_score:.2f})"]
            if record.title:
                evidence_parts.append(f"Article title: {record.title[:80]}")
            if record.year:
                evidence_parts.append(f"Year: {record.year}")
            if record.authors:
                evidence_parts.append(f"Authors: {record.as_author_list()[:80]}")

            needs_review = best_score < 0.92
            return MatchResult(
                method=MatchMethod.TITLE_AUTHOR_YEAR_FUZZY,
                confidence=best_score,
                matched_id=best_match.match_key() if best_match else "",
                evidence=evidence_parts,
                needs_review=needs_review,
            )

        return None
