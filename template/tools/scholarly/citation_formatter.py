"""Citation formatter — GB/T 7714, APA 7, BibTeX, RIS from unified ScholarlyRecord.

Architecture:
  - All records first converted to CSL-JSON (canonical intermediate format).
  - citeproc-py is the preferred renderer for CSL styles, but is OPTIONAL.
  - GBT7714FallbackFormatter provides reliable GB/T 7714 journal-article output
    when citeproc-py is not installed or fails golden tests.
  - BibTeX and RIS are generated directly from the data model, not from
    external API raw content.
  - Unsupported document types are explicitly marked as unsupported.

CSL-JSON spec: https://github.com/citation-style-language/schema
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .models import CitationData, CitationEngine, CitationStyle, ScholarlyRecord, SourceStatus

# ─────────────────────────────────────────────
# Optional citeproc-py detection
# ─────────────────────────────────────────────

try:
    import citeproc  # noqa: F401
    from citeproc import CitationStylesStyle, CitationStylesBibliography, Citation, formatter
    from citeproc.source.json import CiteProcJSON
    HAS_CITEPROC = True
    CITEPROC_VERSION = getattr(citeproc, '__version__', 'unknown')
except ImportError:
    HAS_CITEPROC = False
    CITEPROC_VERSION = "not installed"


# ─────────────────────────────────────────────
# CSL-JSON conversion
# ─────────────────────────────────────────────

def to_csl_json(record: ScholarlyRecord) -> Dict[str, Any]:
    """Convert a ScholarlyRecord to CSL-JSON format.

    CSL types: article-journal, article, book, chapter, thesis, etc.
    Phase 1A: only journal-article is reliably tested.
    """
    csl: Dict[str, Any] = {
        "id": record.doi or f"pkb-{hash(record.title) & 0x7fffffff:08x}",
        "type": record.pub_type or "article-journal",
    }

    if record.title:
        csl["title"] = record.title
    if record.journal_name:
        csl["container-title"] = record.journal_name
    if record.volume:
        csl["volume"] = record.volume
    if record.issue:
        csl["issue"] = record.issue
    if record.page:
        csl["page"] = record.page
    if record.article_number:
        csl["article-number"] = record.article_number
    if record.doi:
        csl["DOI"] = record.doi
    if record.issn_l:
        csl["ISSN"] = record.issn_l
    elif record.issn:
        csl["ISSN"] = record.issn[0]
    if record.publisher:
        csl["publisher"] = record.publisher

    # Authors
    if record.authors:
        csl["author"] = []
        for a in record.authors:
            entry: Dict[str, str] = {}
            if a.get("family"):
                entry["family"] = a["family"]
            if a.get("given"):
                entry["given"] = a["given"]
            if entry:
                csl["author"].append(entry)

    # Date
    if record.year:
        csl["issued"] = {"date-parts": [[record.year]]}

    return csl


# ─────────────────────────────────────────────
# GB/T 7714 Fallback Formatter
# ─────────────────────────────────────────────

class CitationFormatterError(Exception):
    """Raised when citation formatting fails."""


class GBT7714FallbackFormatter:
    """Reliable GB/T 7714-2015 numeric (顺序编码制) formatter for journal articles.

    This is a fallback used when citeproc-py is not installed or fails
    the golden tests for GB/T 7714. Phase 1A only reliably supports
    journal articles (期刊文章 [J]).

    Per GB/T 7714-2015 §8.1.1, journal article format:
      顺序编码制 (numeric):
        作者. 题名[J]. 刊名, 年, 卷(期): 页码.
      著者-出版年 (author-date):
        作者. (年). 题名[J]. 刊名, 卷(期): 页码.

    Rules implemented:
      - ≤3 authors: all listed. >3 authors: first 3 + "等" (Chinese) or "et al."
      - Journal name and year are separated by ", " (comma-space).
      - DOI is NOT included in numeric/author-date output per GB/T 7714 convention.
      - Online-first articles without vol/issue/page are formatted with year only.
      - Unsupported types return explicit [UNSUPPORTED TYPE: …] marker.
    """

    # Supported CSL types
    SUPPORTED_TYPES = {"article-journal", "article"}

    # ── Public API ──

    def format_numeric(self, record: ScholarlyRecord) -> CitationData:
        """Generate GB/T 7714-2015 numeric-style (顺序编码制) citation.

        Format: 作者. 题名[J]. 刊名, 年, 卷(期): 页码.
        """
        if record.pub_type not in self.SUPPORTED_TYPES:
            return CitationData(
                style=CitationStyle.GBT7714_NUMERIC,
                formatted=f"[UNSUPPORTED TYPE: {record.pub_type}]",
                status=SourceStatus.UNAVAILABLE,
            )

        # Front matter: 作者. 题名[J]
        front = self._build_front_matter(record)

        # Publication info: 刊名, 年, 卷(期): 页码
        pub_info = self._build_pub_info(record)

        if front and pub_info:
            citation = f"{front}. {pub_info}."
        elif front:
            citation = f"{front}."
        else:
            citation = f"{pub_info}."

        return CitationData(
            style=CitationStyle.GBT7714_NUMERIC,
            formatted=citation,
            csl_json=to_csl_json(record),
            engine_used="fallback",
            strict=True,
        )

    def format_author_date(self, record: ScholarlyRecord) -> CitationData:
        """Generate GB/T 7714-2015 author-date (著者-出版年) citation.

        Format: 作者. (年). 题名[J]. 刊名, 卷(期): 页码.
        """
        if record.pub_type not in self.SUPPORTED_TYPES:
            return CitationData(
                style=CitationStyle.GBT7714_AUTHOR_DATE,
                formatted=f"[UNSUPPORTED TYPE: {record.pub_type}]",
                status=SourceStatus.UNAVAILABLE,
            )

        # Front matter: 作者. (年). 题名[J]
        author_str = self._format_authors_gbt(record.authors)
        year_str = f"({record.year})" if record.year else "(n.d.)"

        front_parts = []
        if author_str:
            front_parts.append(author_str)
        front_parts.append(year_str)
        if record.title:
            front_parts.append(f"{record.title}[J]")

        front = ". ".join(p.strip() for p in front_parts if p.strip())

        # Publication info: 刊名, 卷(期): 页码 (without year, already in front)
        pub_info = self._build_pub_info_no_year(record)

        if front and pub_info:
            citation = f"{front}. {pub_info}."
        elif front:
            citation = f"{front}."
        else:
            citation = f"{pub_info}."

        return CitationData(
            style=CitationStyle.GBT7714_AUTHOR_DATE,
            formatted=citation,
            csl_json=to_csl_json(record),
            engine_used="fallback",
            strict=True,
        )

    # ── Internal helpers ──

    @staticmethod
    def _format_authors_gbt(authors: List[Dict[str, str]]) -> str:
        """Format author list per GB/T 7714-2015 rules.

        - Chinese (CJK): family+given, no space, e.g. 张三
        - Non-Chinese: family + abbreviated given initials, e.g. Smith J
        - ≤3 authors: list all separated by ", "
        - >3 authors: first 3 + "等" / "et al." depending on first-author script

        GB/T 7714-2015 §8.1.1: 著作方式相同的责任者不超过3个时，全部照录。
        超过3个时，著录前3个责任者，其后加"等"或"et al."。
        """
        if not authors:
            return ""

        formatted = []
        for a in authors:
            family = a.get("family", "").strip()
            given = a.get("given", "").strip()
            if not family:
                continue
            # Detect if Chinese (any CJK character)
            has_cjk = bool(re.search(r'[一-鿿㐀-䶿]', family + given))
            if has_cjk:
                # Chinese: family + given, no space
                formatted.append(f"{family}{given}")
            else:
                # Non-Chinese: family + abbreviated given initials (no period)
                if given:
                    initials = ' '.join(g[0].upper() for g in given.split() if g)
                    formatted.append(f"{family} {initials}")
                else:
                    formatted.append(family)

        if len(formatted) > 3:
            # Determine truncation marker from first author's script
            first_author = authors[0]
            first_family = first_author.get("family", "")
            first_given = first_author.get("given", "")
            first_has_cjk = bool(re.search(r'[一-鿿㐀-䶿]', first_family + first_given))
            # "et al" without period — the citation structure adds the period
            # between the author block and the title.
            marker = "等" if first_has_cjk else "et al"
            formatted = formatted[:3]
            formatted.append(marker)

        return ", ".join(formatted)

    @staticmethod
    def _build_front_matter(record: ScholarlyRecord) -> str:
        """Build '作者. 题名[J]' portion."""
        parts = []
        author_str = GBT7714FallbackFormatter._format_authors_gbt(record.authors)
        if author_str:
            parts.append(author_str)
        if record.title:
            parts.append(f"{record.title}[J]")
        return ". ".join(p.strip() for p in parts if p.strip())

    @staticmethod
    def _build_pub_info(record: ScholarlyRecord) -> str:
        """Build '刊名, 年, 卷(期): 页码' portion for numeric style.

        Per GB/T 7714-2015:
          - With volume:     年, 卷(期): 页码
          - No volume, issue: 年(期): 页码
          - No vol, no issue: 年: 页码
        """
        parts = []

        if record.journal_name:
            parts.append(record.journal_name)

        # Year
        year_str = str(record.year) if record.year else ""

        # Vol(issue) — issue attaches to volume when present, to year otherwise
        vol_issue = ""
        if record.volume:
            vol_issue = record.volume
            if record.issue:
                vol_issue += f"({record.issue})"

        # Page or article number
        page_str = record.page if record.page else (record.article_number if record.article_number else "")

        # Build: year[, vol(issue)][(issue)][: page]
        combined = year_str
        if vol_issue:
            combined += f", {vol_issue}"
        elif record.issue and not record.volume:
            # Issue goes in parens directly after year when no volume
            combined += f"({record.issue})"
        if page_str:
            combined += f": {page_str}" if combined else page_str

        if combined:
            parts.append(combined)

        return ", ".join(p.strip() for p in parts if p.strip())

    @staticmethod
    def _build_pub_info_no_year(record: ScholarlyRecord) -> str:
        """Build '刊名, 卷(期): 页码' portion for author-date style (year already in front matter)."""
        parts = []

        if record.journal_name:
            parts.append(record.journal_name)

        # Vol(issue) — issue attaches to volume when present
        vol_issue = ""
        if record.volume:
            vol_issue = record.volume
            if record.issue:
                vol_issue += f"({record.issue})"
        elif record.issue:
            # No volume — issue goes in parens directly
            vol_issue = f"({record.issue})"

        # Page or article number
        page_str = record.page if record.page else (record.article_number if record.article_number else "")

        combined = vol_issue
        if page_str:
            combined += f": {page_str}" if combined else page_str

        if combined:
            parts.append(combined)

        return ", ".join(p.strip() for p in parts if p.strip())


class APA7FallbackFormatter:
    """Fallback APA 7 formatter for journal articles."""

    SUPPORTED_TYPES = {"article-journal", "article"}

    def format(self, record: ScholarlyRecord) -> CitationData:
        """Generate APA 7 citation."""
        if record.pub_type not in self.SUPPORTED_TYPES:
            return CitationData(
                style=CitationStyle.APA7,
                formatted=f"[UNSUPPORTED TYPE: {record.pub_type}]",
                status=SourceStatus.UNAVAILABLE,
            )

        authors_str = self._format_authors_apa(record.authors)
        year_str = f"({record.year})" if record.year else "(n.d.)"
        title = record.title + "." if record.title else ""
        journal = f"*{record.journal_name}*" if record.journal_name else ""
        vol_issue = ""
        if record.volume:
            vol_issue = f", *{record.volume}*"
            if record.issue:
                vol_issue += f"({record.issue})"
        page = f", {record.page}" if record.page else ""
        doi = f". https://doi.org/{record.doi}" if record.doi else ""

        citation = f"{authors_str} {year_str}. {title} {journal}{vol_issue}{page}{doi}"
        citation = re.sub(r'\s+', ' ', citation).strip()

        return CitationData(
            style=CitationStyle.APA7,
            formatted=citation,
            csl_json=to_csl_json(record),
        )

    @staticmethod
    def _format_authors_apa(authors: List[Dict[str, str]]) -> str:
        """APA 7 author formatting."""
        if not authors:
            return ""
        formatted = []
        for a in authors:
            family = a.get("family", "").strip()
            given = a.get("given", "").strip()
            if not family:
                continue
            initials = '. '.join(g[0].upper() for g in given.split() if g) + '.' if given else ''
            formatted.append(f"{family}, {initials}" if initials else family)

        n = len(formatted)
        if n == 1:
            return formatted[0]
        elif n == 2:
            return f"{formatted[0]}, & {formatted[1]}"
        elif n <= 7:
            return ', '.join(formatted[:-1]) + f", & {formatted[-1]}"
        else:
            return ', '.join(formatted[:6]) + f", ... {formatted[-1]}"


# ─────────────────────────────────────────────
# BibTeX exporter
# ─────────────────────────────────────────────

def export_bibtex(record: ScholarlyRecord, cite_key: str = "") -> CitationData:
    """Export a ScholarlyRecord as BibTeX.

    Generates a cite key from author+year+title if none provided.
    Does NOT return raw Crossref/OpenAlex content.
    """
    if not cite_key:
        cite_key = _make_bibtex_key(record)

    entry_type = "article"  # default
    if record.pub_type in ("article-journal", "article"):
        entry_type = "article"
    elif "book" in record.pub_type:
        entry_type = "book"
    elif "chapter" in record.pub_type:
        entry_type = "incollection"
    elif "thesis" in record.pub_type:
        entry_type = "phdthesis"

    lines = [f"@{entry_type}{{{cite_key},"]

    if record.title:
        lines.append(f"  title = {{{record.title}}},")
    authors_bib = _format_authors_bibtex(record.authors)
    if authors_bib:
        lines.append(f"  author = {{{authors_bib}}},")
    if record.journal_name:
        lines.append(f"  journal = {{{record.journal_name}}},")
    if record.year:
        lines.append(f"  year = {{{record.year}}},")
    if record.volume:
        lines.append(f"  volume = {{{record.volume}}},")
    if record.issue:
        lines.append(f"  number = {{{record.issue}}},")
    if record.page:
        lines.append(f"  pages = {{{record.page}}},")
    if record.doi:
        lines.append(f"  doi = {{{record.doi}}},")
    if record.publisher:
        lines.append(f"  publisher = {{{record.publisher}}},")
    if record.issn_l:
        lines.append(f"  issn = {{{record.issn_l}}},")

    lines.append("}")

    bibtex = "\n".join(lines)

    return CitationData(
        style=CitationStyle.BIBTEX,
        formatted=bibtex,
        csl_json=to_csl_json(record),
    )


def _make_bibtex_key(record: ScholarlyRecord) -> str:
    """Generate a BibTeX cite key from author + year + title."""
    parts = []
    if record.authors:
        first = record.authors[0].get("family", "").strip()
        if first:
            # Take first 6 chars of family name
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', first)
            parts.append(cleaned[:6].lower() or "author")
    if record.year:
        parts.append(str(record.year))
    if record.title:
        # First meaningful word from title
        words = re.findall(r'[a-zA-Z]+', record.title)
        if words:
            parts.append(words[0].lower())
    if not parts:
        parts.append("ref")
    return "".join(parts)


def _format_authors_bibtex(authors: List[Dict[str, str]]) -> str:
    """Format authors for BibTeX: Last, First and Last, First"""
    formatted = []
    for a in authors:
        family = a.get("family", "").strip()
        given = a.get("given", "").strip()
        if family and given:
            formatted.append(f"{family}, {given}")
        elif family:
            formatted.append(family)
    return " and ".join(formatted)


# ─────────────────────────────────────────────
# RIS exporter
# ─────────────────────────────────────────────

def export_ris(record: ScholarlyRecord) -> CitationData:
    """Export a ScholarlyRecord as RIS format.

    Does NOT return raw Crossref/OpenAlex content.
    """
    lines = []

    # Type
    ty_map = {
        "article-journal": "JOUR",
        "article": "JOUR",
        "book": "BOOK",
        "chapter": "CHAP",
        "thesis": "THES",
    }
    lines.append(f"TY  - {ty_map.get(record.pub_type, 'JOUR')}")

    if record.title:
        lines.append(f"TI  - {record.title}")
    for a in record.authors:
        family = a.get("family", "").strip()
        given = a.get("given", "").strip()
        if family:
            lines.append(f"AU  - {given} {family}".strip() if given else f"AU  - {family}")
    if record.journal_name:
        lines.append(f"JO  - {record.journal_name}")
    # Also as T2/JF (journal full name)
    if record.journal_name:
        lines.append(f"JF  - {record.journal_name}")
    if record.year:
        lines.append(f"PY  - {record.year}")
    if record.volume:
        lines.append(f"VL  - {record.volume}")
    if record.issue:
        lines.append(f"IS  - {record.issue}")
    if record.page:
        lines.append(f"SP  - {record.page.split('-')[0] if '-' in record.page else record.page}")
        if '-' in record.page:
            lines.append(f"EP  - {record.page.split('-')[1]}")
    if record.doi:
        lines.append(f"DO  - {record.doi}")
    if record.issn_l:
        lines.append(f"SN  - {record.issn_l}")
    elif record.issn:
        lines.append(f"SN  - {record.issn[0]}")
    if record.publisher:
        lines.append(f"PB  - {record.publisher}")

    lines.append("ER  - ")

    ris = "\n".join(lines)

    return CitationData(
        style=CitationStyle.RIS,
        formatted=ris,
        csl_json=to_csl_json(record),
    )


# ─────────────────────────────────────────────
# Citeproc-based formatter (uses citeproc-py when available)
# ─────────────────────────────────────────────

class CiteprocFormatter:
    """CSL-based citation formatter using citeproc-py.

    Requires citeproc-py to be installed. Falls back to
    GBT7714FallbackFormatter when unavailable or on error.

    Looks for CSL style files in:
      1. .pkb_local/scholarly/styles/  (user-provided)
      2. citeproc-py's bundled styles
    """

    # CSL style identifiers (names recognised by citeproc-py-styles)
    GBT7714_NUMERIC_STYLE = "china-national-standard-gb-t-7714-2015-numeric"
    GBT7714_AUTHOR_DATE_STYLE = "china-national-standard-gb-t-7714-2015-author-date"
    APA7_STYLE = "apa"

    def __init__(self, styles_dir: Optional[str] = None):
        if not HAS_CITEPROC:
            raise CitationFormatterError("citeproc-py is not installed")
        self._styles_dir = styles_dir
        self._styles: Dict[str, Any] = {}

    def _load_style(self, style_name: str) -> Any:
        """Load a CSL style by name. Returns None if not found."""
        if style_name in self._styles:
            return self._styles[style_name]
        try:
            # Use citeproc-py-styles to resolve the style file path
            try:
                import citeproc_styles
                style_path = citeproc_styles.get_style_filepath(style_name)
            except (ImportError, Exception):
                style_path = None
            if not style_path:
                return None
            style = CitationStylesStyle(style_path)
            self._styles[style_name] = style
            return style
        except Exception:
            return None

    def _format_with_csl(self, record: ScholarlyRecord, style_name: str,
                         style_enum: CitationStyle) -> CitationData:
        """Format a record using a CSL style via citeproc-py."""
        style = self._load_style(style_name)
        if style is None:
            return CitationData(
                style=style_enum,
                formatted=f"[CSL STYLE NOT FOUND: {style_name}]",
                status=SourceStatus.UNAVAILABLE,
            )

        csl_data = to_csl_json(record)
        item_id = csl_data.get("id", "item-1")

        try:
            from citeproc import CitationItem

            # citeproc-py's CiteProcJSON takes a list of CSL-JSON items
            bib_source = CiteProcJSON([csl_data])
            bibliography = CitationStylesBibliography(
                style, bib_source, formatter.html
            )

            # Register the citation
            citation = Citation([CitationItem(item_id)])
            bibliography.register(citation)

            # Generate bibliography entries
            bib_result = bibliography.bibliography()

            if not bib_result:
                return CitationData(
                    style=style_enum,
                    formatted="[CITATION RENDER FAILED: no output]",
                    status=SourceStatus.ERROR,
                )

            # bib_result is a list of strings (HTML formatted)
            import re as _re
            text = _re.sub(r'<[^>]+>', '', str(bib_result[0])).strip()

            return CitationData(
                style=style_enum,
                formatted=text,
                csl_json=csl_data,
            )
        except Exception as e:
            return CitationData(
                style=style_enum,
                formatted=f"[CITEPROC ERROR: {e}]",
                status=SourceStatus.ERROR,
            )

    def format_numeric(self, record: ScholarlyRecord) -> CitationData:
        """GB/T 7714 numeric via citeproc."""
        if record.pub_type not in GBT7714FallbackFormatter.SUPPORTED_TYPES:
            return CitationData(
                style=CitationStyle.GBT7714_NUMERIC,
                formatted=f"[UNSUPPORTED TYPE: {record.pub_type}]",
                status=SourceStatus.UNAVAILABLE,
            )
        return self._format_with_csl(record, self.GBT7714_NUMERIC_STYLE,
                                      CitationStyle.GBT7714_NUMERIC)

    def format_author_date(self, record: ScholarlyRecord) -> CitationData:
        """GB/T 7714 author-date via citeproc."""
        if record.pub_type not in GBT7714FallbackFormatter.SUPPORTED_TYPES:
            return CitationData(
                style=CitationStyle.GBT7714_AUTHOR_DATE,
                formatted=f"[UNSUPPORTED TYPE: {record.pub_type}]",
                status=SourceStatus.UNAVAILABLE,
            )
        return self._format_with_csl(record, self.GBT7714_AUTHOR_DATE_STYLE,
                                      CitationStyle.GBT7714_AUTHOR_DATE)

    def format_apa(self, record: ScholarlyRecord) -> CitationData:
        """APA 7 via citeproc."""
        if record.pub_type not in GBT7714FallbackFormatter.SUPPORTED_TYPES:
            return CitationData(
                style=CitationStyle.APA7,
                formatted=f"[UNSUPPORTED TYPE: {record.pub_type}]",
                status=SourceStatus.UNAVAILABLE,
            )
        return self._format_with_csl(record, self.APA7_STYLE, CitationStyle.APA7)


# ─────────────────────────────────────────────
# Unified citation formatter interface
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# Engine routing rules
# ─────────────────────────────────────────────

# Styles where the fallback formatter has been verified against golden tests
_GB_T_STYLES = {CitationStyle.GBT7714_NUMERIC, CitationStyle.GBT7714_AUTHOR_DATE}

# Styles that can use citeproc when auto + available (non-GB/T CSL styles)
_CITEPROC_PREFERRED_STYLES = {CitationStyle.APA7}

_CITEPROC_GB_T_WARNING = (
    "citeproc-py GB/T output has known locale and name-format differences"
)


class CitationFormatter:
    """Top-level citation formatter with explicit engine selection.

    Engine routing (CitationEngine):
      - AUTO (default):
          * GB/T 7714 + journal article → fallback (golden-verified).
          * GB/T 7714 + non-journal-article → try fallback first;
            if UNSUPPORTED, try citeproc with strict=False + warning.
          * APA 7 → citeproc only (no validated APA fallback exists).
            - citeproc available + success → citeproc (strict=True).
            - citeproc not installed → UNAVAILABLE (no fallback).
            - citeproc fails → ERROR (no fallback).
          * BibTeX / RIS → direct (always from data model).
      - FALLBACK:
          * GB/T 7714 → fallback formatter.
          * APA 7 → UNSUPPORTED (no validated APA fallback exists).
          * Other styles → unsupported.
      - CITEPROC: force citeproc for all CSL styles. Failure → ERROR,
        no silent fallback. GB/T output always strict=False.
    """

    def __init__(self, engine: CitationEngine = CitationEngine.AUTO):
        self._engine = engine
        self._use_citeproc = HAS_CITEPROC
        self._citeproc_fmt = None
        if self._use_citeproc:
            try:
                self._citeproc_fmt = CiteprocFormatter()
            except Exception:
                self._use_citeproc = False
        self.gbt = GBT7714FallbackFormatter()
        self.apa = APA7FallbackFormatter()

    @property
    def engine(self) -> CitationEngine:
        return self._engine

    # ── Public API ──

    def format(self, record: ScholarlyRecord, style: CitationStyle) -> CitationData:
        """Format a record in the requested style per the configured engine."""
        style_str = style.value

        # ── BibTeX / RIS: always direct from data model ──
        if style == CitationStyle.BIBTEX:
            return self._wrap_direct(export_bibtex(record), style_str)
        if style == CitationStyle.RIS:
            return self._wrap_direct(export_ris(record), style_str)

        # ── Route by engine ──
        if self._engine == CitationEngine.FALLBACK:
            return self._route_fallback(record, style, style_str)
        elif self._engine == CitationEngine.CITEPROC:
            return self._route_citeproc_forced(record, style, style_str)
        else:  # AUTO
            return self._route_auto(record, style, style_str)

    def format_all(self, record: ScholarlyRecord) -> List[CitationData]:
        """Generate citations in all supported styles."""
        results = []
        for style in [CitationStyle.GBT7714_NUMERIC, CitationStyle.GBT7714_AUTHOR_DATE,
                      CitationStyle.APA7, CitationStyle.BIBTEX, CitationStyle.RIS]:
            results.append(self.format(record, style))
        return results

    # ── Routing helpers ──

    def _route_auto(self, record, style, style_str):
        """AUTO mode: select engine per style."""
        is_gbt = style in _GB_T_STYLES
        is_journal = record.pub_type in GBT7714FallbackFormatter.SUPPORTED_TYPES

        if is_gbt and is_journal:
            # GB/T journal article → fallback (golden-verified)
            return self._call_fallback(record, style, style_str)

        if is_gbt and not is_journal:
            # GB/T non-journal-article → try fallback first
            fb = self._call_fallback(record, style, style_str)
            if fb.status == SourceStatus.AVAILABLE:
                return fb
            # Fallback doesn't support this type → try citeproc with warning
            if self._use_citeproc:
                cp = self._call_citeproc(record, style, style_str)
                if cp.status == SourceStatus.AVAILABLE:
                    return CitationData(
                        style=style, formatted=cp.formatted,
                        csl_json=cp.csl_json, status=cp.status,
                        engine_used="citeproc", style_requested=style_str,
                        strict=False,
                        warnings=[_CITEPROC_GB_T_WARNING],
                    )
            # Neither supports it
            return fb

        if style in _CITEPROC_PREFERRED_STYLES:
            # APA 7 → citeproc only. No validated APA fallback exists.
            if self._use_citeproc:
                cp = self._call_citeproc(record, style, style_str)
                if cp.status == SourceStatus.AVAILABLE:
                    return CitationData(
                        style=style, formatted=cp.formatted,
                        csl_json=cp.csl_json, status=cp.status,
                        engine_used="citeproc", style_requested=style_str,
                        strict=True, warnings=[],
                    )
                # Citeproc formatting failed → ERROR, no silent fallback
                return CitationData(
                    style=style, formatted=cp.formatted,
                    csl_json=cp.csl_json, status=SourceStatus.ERROR,
                    engine_used="citeproc", style_requested=style_str,
                    strict=False,
                    warnings=["citeproc-py failed to produce valid APA 7 output"],
                )
            # Citeproc not installed → UNAVAILABLE, no fallback
            return CitationData(
                style=style,
                formatted="[CITEPROC REQUIRED: APA 7 formatting requires citeproc-py; "
                           "no validated APA fallback is available]",
                status=SourceStatus.UNAVAILABLE,
                engine_used="", style_requested=style_str,
                strict=False,
                warnings=["APA 7 formatting requires citeproc-py; "
                           "no validated APA fallback is available"],
            )

        # Fallback for anything else
        return self._call_fallback(record, style, style_str)

    def _route_fallback(self, record, style, style_str):
        """FALLBACK mode: force fallback. APA → UNSUPPORTED (unvalidated)."""
        if style in _CITEPROC_PREFERRED_STYLES:
            return CitationData(
                style=style,
                formatted="[UNSUPPORTED: APA 7 fallback is not implemented — "
                           "only GB/T 7714 journal articles are validated]",
                status=SourceStatus.UNAVAILABLE,
                engine_used="fallback", style_requested=style_str,
                strict=False,
                warnings=["The fallback formatter currently supports validated "
                           "GB/T 7714 journal articles only"],
            )
        return self._call_fallback(record, style, style_str)

    def _route_citeproc_forced(self, record, style, style_str):
        """CITEPROC mode: force citeproc. Failure → ERROR, no silent fallback."""
        is_gbt = style in _GB_T_STYLES
        if not self._use_citeproc:
            return CitationData(
                style=style,
                formatted="[CITEPROC UNAVAILABLE: citeproc-py not installed]",
                status=SourceStatus.ERROR,
                engine_used="citeproc", style_requested=style_str,
                strict=False,
                warnings=["citeproc-py is not installed"],
            )
        cp = self._call_citeproc(record, style, style_str)
        if cp.status != SourceStatus.AVAILABLE:
            return CitationData(
                style=style, formatted=cp.formatted,
                csl_json=cp.csl_json, status=SourceStatus.ERROR,
                engine_used="citeproc", style_requested=style_str,
                strict=False,
                warnings=["citeproc-py failed to produce valid output"],
            )
        return CitationData(
            style=style, formatted=cp.formatted,
            csl_json=cp.csl_json, status=cp.status,
            engine_used="citeproc", style_requested=style_str,
            strict=not is_gbt,  # GB/T via citeproc is never strict
            warnings=[_CITEPROC_GB_T_WARNING] if is_gbt else [],
        )

    # ── Low-level call helpers ──

    def _call_fallback(self, record, style, style_str):
        """Call the appropriate fallback formatter and wrap with metadata."""
        if style == CitationStyle.GBT7714_NUMERIC:
            result = self.gbt.format_numeric(record)
        elif style == CitationStyle.GBT7714_AUTHOR_DATE:
            result = self.gbt.format_author_date(record)
        elif style == CitationStyle.APA7:
            result = self.apa.format(record)
        else:
            return CitationData(
                style=style,
                formatted=f"[UNSUPPORTED STYLE: {style.value}]",
                status=SourceStatus.UNAVAILABLE,
                engine_used="fallback", style_requested=style_str,
                strict=True, warnings=[],
            )
        return CitationData(
            style=result.style, formatted=result.formatted,
            csl_json=result.csl_json, status=result.status,
            engine_used="fallback", style_requested=style_str,
            strict=True, warnings=[],
        )

    def _call_citeproc(self, record, style, style_str):
        """Call citeproc formatter (raw, no metadata wrapping)."""
        if style == CitationStyle.GBT7714_NUMERIC:
            return self._citeproc_fmt.format_numeric(record)
        elif style == CitationStyle.GBT7714_AUTHOR_DATE:
            return self._citeproc_fmt.format_author_date(record)
        elif style == CitationStyle.APA7:
            return self._citeproc_fmt.format_apa(record)
        else:
            return CitationData(
                style=style,
                formatted=f"[UNSUPPORTED STYLE: {style.value}]",
                status=SourceStatus.UNAVAILABLE,
            )

    @staticmethod
    def _wrap_direct(result, style_str):
        """Wrap BibTeX/RIS output with direct engine metadata."""
        return CitationData(
            style=result.style, formatted=result.formatted,
            csl_json=result.csl_json, status=result.status,
            engine_used="direct", style_requested=style_str,
            strict=True, warnings=[],
        )
