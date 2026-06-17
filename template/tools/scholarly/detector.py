"""Scholarly literature detector — identifies whether a Markdown page
represents a scholarly work (journal article, conference paper, preprint, thesis).

Uses a priority-ordered evidence architecture:
  1. Explicit user declarations (type: literature, scholarly.detected: true)
     → Always scholarly unless scholarly.disabled: true
  2. Verified structural strong signals (DOI, arXiv, PMID, ISSN+author+year,
     complete journal metadata with vol/issue/pages)
     → Overridden only by hard exclusions (page-type judgment)
     → Soft exclusions (keywords) reduce confidence but do NOT negate
  3. Medium signals (bibliographic fields, structure markers, filename)
  4. Hard exclusions (TOC, search results, aggregation lists, news site pages,
     software README/changelog, citation-list-only)
  5. Soft exclusions (title keywords, content patterns) — reduce confidence only

Phase 1B.1: fixed priority to prevent keyword exclusions from overriding
explicit user declarations and verified scholarly identifiers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ─────────────────────────────────────────────
# Detection result
# ─────────────────────────────────────────────

@dataclass
class ScholarlyDetectionResult:
    """Output of the scholarly literature detector.

    Attributes:
        is_scholarly: Whether the page is a scholarly work.
        confidence: 0.0–1.0 confidence score.
        reasons: Human-readable reasons for the classification.
        identifiers: Extracted identifiers (doi, arxiv_id, pmid, etc.).
        detected_type: Broad type category (article-journal, paper-conference,
                       thesis, preprint, book, chapter, report, unknown).
        strong_signals: Which strong signals were found.
        medium_signals: Which medium signals were found.
        hard_exclusion_signals: Hard exclusion signals found (page-type judgment).
        soft_exclusion_signals: Soft exclusion signals found (keyword-based).
        user_declared: Whether user explicitly declared this as scholarly.
        user_disabled: Whether user explicitly disabled scholarly processing.
    """
    is_scholarly: bool = False
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    identifiers: Dict[str, str] = field(default_factory=dict)
    detected_type: str = "unknown"
    strong_signals: List[str] = field(default_factory=list)
    medium_signals: List[str] = field(default_factory=list)
    hard_exclusion_signals: List[str] = field(default_factory=list)
    soft_exclusion_signals: List[str] = field(default_factory=list)
    user_declared: bool = False
    user_disabled: bool = False


# ─────────────────────────────────────────────
# Signal definitions
# ─────────────────────────────────────────────

# Patterns for identifier extraction
DOI_PATTERN = re.compile(
    r'\b(10\.\d{4,}(?:\.\d+)?\/\S+(?:(?!["\'])\S))\b',
    re.IGNORECASE,
)
ARXIV_PATTERN = re.compile(
    r'\b(arXiv:\s*\d{4}\.\d{4,}(?:v\d+)?)\b',
    re.IGNORECASE,
)
PMID_PATTERN = re.compile(
    r'\b(PMID:\s*\d{5,8})\b',
    re.IGNORECASE,
)

# Academic source domains / URL patterns
ACADEMIC_DOMAINS = {
    "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "doi.org",
    "sci-hub", "scholar.google.com", "semanticscholar.org",
    "researchgate.net", "academia.edu",
    "cnki.net", "wanfangdata.com", "cqvip.com",
    "ieeexplore.ieee.org", "dl.acm.org", "springer.com",
    "sciencedirect.com", "tandfonline.com", "wiley.com",
    "nature.com", "science.org", "cell.com", "lancet.com",
    "nejm.org", "jamanetwork.com", "bmj.com",
    "ssrn.com", "repec.org", "nber.org",
    "thesis", "dissertation",
}

# Journal article structure indicators (Chinese)
SCHOLARLY_STRUCTURE_CN = {
    "摘要", "关键词", "参考文献", "引用文献",
    "作者简介", "基金项目", "收稿日期", "中图分类号",
    "通讯作者", "第一作者",
}

# Journal article structure indicators (English)
SCHOLARLY_STRUCTURE_EN = {
    "abstract", "keywords", "references", "bibliography",
    "introduction", "methodology", "method", "results",
    "discussion", "conclusion", "acknowledgments",
    "corresponding author", "funding",
}

# Journal bibliographic field keys
BIBLIOGRAPHIC_FIELDS = {
    "volume", "issue", "pages", "article_number",
    "issn", "eissn", "issn_l",
}

# ─────────────────────────────────────────────
# Hard exclusions — page-type judgment
# These reflect the PAGE'S OWN TYPE, not keywords.
# They CAN override strong signals (except explicit user declarations).
# ─────────────────────────────────────────────

# Hard exclusion: page IS a journal TOC / issue listing
HARD_EXCLUSION_PATTERNS = [
    # Journal issue table of contents
    (re.compile(p, re.IGNORECASE), "journal_toc") for p in [
        r'^(?:本期)?目录\s*$',
        r'^table\s+of\s+contents\s*$',
        r'^(?:vol(?:ume)?\.?\s*\d+.*?(?:issue|no\.?)\s*\d+.*?(?:table\s+of\s+)?contents?)',
        r'^(?:第\d+卷.*?第\d+期.*?(?:目录|总目录))',
    ]
] + [
    # Search results page
    (re.compile(p, re.IGNORECASE), "search_results") for p in [
        r'^检索结果',
        r'^search\s+results?\s+(?:for|：)',
        r'^\d+\s+results?\s+found',
    ]
] + [
    # Multi-paper aggregation / list (not a single paper)
    (re.compile(p, re.IGNORECASE), "paper_aggregation") for p in [
        r'(?:最新|top|recent)\s*(?:论文|papers?|articles?)\s*(?:推荐|列表|list)',
        r'^\s*(?:\[\d+\]\s+.+\n){3,}',  # 3+ citation-style entries
    ]
] + [
    # Software README / changelog
    (re.compile(p, re.IGNORECASE), "software_doc") for p in [
        r'^(?:#+\s*)?(?:readme|changelog|license)(?:\s*$|\s*\n)',
        r'(?:npm\s+(?:install|run|test)|pip\s+install|gem\s+install|cargo\s+build)',
    ]
]

# ─────────────────────────────────────────────
# Soft exclusions — keyword-based
# These reduce confidence but do NOT override:
#   - Explicit user declarations (type: literature, scholarly.detected: true)
#   - Verified structural strong signals (DOI, ISSN+author+year, arXiv, PMID)
# ─────────────────────────────────────────────

SOFT_EXCLUSION_TITLE_CN = {
    "新闻", "报道", "快讯", "通知", "公告",
}

SOFT_EXCLUSION_TITLE_EN = {
    "news", "press release", "blog", "newsletter", "announcement",
}

SOFT_EXCLUSION_CONTENT_PATTERNS = [
    (re.compile(p, re.IGNORECASE), tag) for p, tag in [
        (r'news\s*article', "news_article"),
        (r'press\s*release', "press_release"),
        (r'blog\s*post', "blog_post"),
        (r'newsletter', "newsletter"),
    ]
]


# ─────────────────────────────────────────────
# Main detection function
# ─────────────────────────────────────────────

def detect_scholarly(
    frontmatter: Dict[str, Any],
    body: str,
    *,
    source_url: str = "",
    file_name: str = "",
    pdf_metadata: Optional[Dict[str, str]] = None,
) -> ScholarlyDetectionResult:
    """Detect whether a Markdown page represents a scholarly work.

    Priority order:
      1. Explicit user declarations (type: literature, scholarly.detected: true)
         → scholarly unless scholarly.disabled: true
      2. Verified structural strong signals → overridden only by hard exclusions
      3. Medium signals → combined with hard/soft exclusion rules
      4. Hard exclusions → negate unless overridden by user declaration
      5. Soft exclusions → reduce confidence; never override strong signals alone

    Args:
        frontmatter: Parsed YAML frontmatter dict.
        body: Page body text (Markdown).
        source_url: Original source URL if available.
        file_name: Original file name.
        pdf_metadata: PDF metadata dict if extracted from a PDF file.

    Returns:
        ScholarlyDetectionResult with classification and confidence.
    """
    reasons: List[str] = []
    identifiers: Dict[str, str] = {}
    strong: List[str] = []
    medium: List[str] = []
    hard_exclusion: List[str] = []
    soft_exclusion: List[str] = []

    # ── Check explicit user declarations first ──
    fm_type = str(frontmatter.get("type", "")).lower()
    fm_scholarly = frontmatter.get("scholarly", {})
    if not isinstance(fm_scholarly, dict):
        fm_scholarly = {}

    user_declared = (fm_type == "literature") or bool(fm_scholarly.get("detected"))
    user_disabled = bool(fm_scholarly.get("disabled", False))

    # ── Extract identifiers from all sources ──
    all_text = body or ""
    fm_texts = []
    for k, v in frontmatter.items():
        if isinstance(v, str):
            fm_texts.append(v)
        elif isinstance(v, dict):
            fm_texts.extend(str(vv) for vv in v.values() if isinstance(vv, str))
    all_text += "\n" + "\n".join(fm_texts)
    if source_url:
        all_text += "\n" + source_url
    if pdf_metadata:
        all_text += "\n" + " ".join(str(v) for v in pdf_metadata.values())

    # DOI
    doi_match = DOI_PATTERN.search(all_text)
    if doi_match:
        identifiers["doi"] = doi_match.group(1).rstrip(".")
        strong.append("doi_identified")

    # arXiv ID
    arxiv_match = ARXIV_PATTERN.search(all_text)
    if arxiv_match:
        identifiers["arxiv_id"] = arxiv_match.group(1)
        strong.append("arxiv_id")

    # PMID
    pmid_match = PMID_PATTERN.search(all_text)
    if pmid_match:
        identifiers["pmid"] = pmid_match.group(1)
        strong.append("pmid")

    # ── Strong signals (in addition to identifiers) ──

    # 1. Frontmatter type: literature
    if fm_type == "literature":
        strong.append("frontmatter_type_literature")
        reasons.append("frontmatter type: literature")

    # 2. Frontmatter scholarly.detected: true
    if fm_scholarly.get("detected"):
        strong.append("scholarly_frontmatter_detected")
        reasons.append("existing scholarly frontmatter block")

    # 3. DOI identified
    if "doi" in identifiers:
        reasons.append(f"DOI identified: {identifiers['doi']}")

    # 4. Academic source URL
    if source_url:
        url_lower = source_url.lower()
        for domain in ACADEMIC_DOMAINS:
            if domain in url_lower:
                strong.append("academic_source_url")
                reasons.append(f"academic source domain: {domain}")
                break

    # 5. PDF metadata contains DOI
    if pdf_metadata:
        pdf_doi = pdf_metadata.get("doi", "") or pdf_metadata.get("DOI", "")
        if pdf_doi and "10." in pdf_doi:
            if "doi" not in identifiers:
                identifiers["doi"] = pdf_doi
            strong.append("pdf_metadata_doi")
            reasons.append("PDF metadata contains DOI")

    # 6. arXiv/PMID identifier
    if "arxiv_id" in identifiers:
        reasons.append(f"arXiv ID: {identifiers['arxiv_id']}")
    if "pmid" in identifiers:
        reasons.append(f"PMID: {identifiers['pmid']}")

    # ── Medium signals ──

    # Title presence
    title = str(frontmatter.get("title", ""))
    if not title:
        h1_match = re.search(r'^#\s+(.+)$', body, re.MULTILINE) if body else None
        if h1_match:
            title = h1_match.group(1).strip()

    has_title = bool(title and len(title) > 3)
    has_authors = bool(frontmatter.get("author") or frontmatter.get("authors"))
    has_year = bool(frontmatter.get("year"))
    has_journal = bool(frontmatter.get("journal") or frontmatter.get("journal_name"))

    # Bibliographic completeness
    bib_score = sum([has_title, has_authors, has_year, has_journal])
    if bib_score >= 3:
        medium.append(f"bibliographic_fields_{bib_score}")
        reasons.append(f"bibliographic fields: title/author/year/journal ({bib_score}/4)")

    # Volume/issue/pages
    vol_fields = 0
    if frontmatter.get("volume"):
        vol_fields += 1
    if frontmatter.get("issue") or frontmatter.get("number"):
        vol_fields += 1
    if frontmatter.get("page") or frontmatter.get("pages"):
        vol_fields += 1
    if frontmatter.get("article_number"):
        vol_fields += 1
    if vol_fields >= 1:
        medium.append(f"volume_issue_page_{vol_fields}")
        reasons.append(f"volume/issue/page fields: {vol_fields}")

    # ISSN / EISSN
    has_issn = bool(frontmatter.get("issn") or frontmatter.get("issn_l") or frontmatter.get("eissn"))
    if has_issn:
        medium.append("has_issn")
        reasons.append("ISSN present")

    # Scholarly structure markers in body
    if body:
        body_lower = body.lower()
        cn_matches = [kw for kw in SCHOLARLY_STRUCTURE_CN if kw in body]
        en_matches = [kw for kw in SCHOLARLY_STRUCTURE_EN if kw in body_lower]
        total_structure = len(cn_matches) + len(en_matches)
        if total_structure >= 2:
            medium.append(f"scholarly_structure_{min(total_structure, 5)}")
            reasons.append(f"scholarly structure markers: {total_structure}")

    # Filename indicates paper
    if file_name:
        fn_lower = file_name.lower()
        paper_indicators = ["paper", "article", "thesis", "dissertation", "preprint",
                           "manuscript", "论文", "文章", "学位"]
        if any(ind in fn_lower for ind in paper_indicators):
            medium.append("filename_indicates_paper")
            reasons.append("filename suggests scholarly work")

    # ── Check hard exclusions (page-type judgment) ──
    title_lower = title.lower()
    body_for_check = body or ""

    for pattern, tag in HARD_EXCLUSION_PATTERNS:
        if pattern.search(title_lower) or pattern.search(body_for_check):
            hard_exclusion.append(f"hard_exclusion:{tag}")
            reasons.append(f"hard exclusion: {tag} (page type)")
            break  # One hard exclusion is enough

    # ── Check soft exclusions (keyword-based) ──
    for kw in SOFT_EXCLUSION_TITLE_CN:
        if kw in title:
            soft_exclusion.append(f"soft_exclusion_title_cn:{kw}")
            reasons.append(f"soft exclusion: title contains '{kw}'")
            break  # One title keyword is enough
    else:
        for kw in SOFT_EXCLUSION_TITLE_EN:
            if kw in title_lower:
                soft_exclusion.append(f"soft_exclusion_title_en:{kw}")
                reasons.append(f"soft exclusion: title contains '{kw}'")
                break

    for pattern, tag in SOFT_EXCLUSION_CONTENT_PATTERNS:
        if pattern.search(body_for_check):
            soft_exclusion.append(f"soft_exclusion_content:{tag}")
            reasons.append(f"soft exclusion: content contains '{tag}'")
            break

    # ── Confidence computation with priority rules ──

    has_strong = len(strong) > 0
    has_medium = len(medium) > 0
    has_hard_exclusion = len(hard_exclusion) > 0
    has_soft_exclusion = len(soft_exclusion) > 0

    # Rule: user_disabled overrides everything
    if user_disabled:
        result = ScholarlyDetectionResult(
            is_scholarly=False,
            confidence=0.0,
            reasons=["scholarly.disabled is true"] + reasons,
            identifiers=identifiers,
            detected_type="unknown",
            strong_signals=strong,
            medium_signals=medium,
            hard_exclusion_signals=hard_exclusion,
            soft_exclusion_signals=soft_exclusion,
            user_declared=user_declared,
            user_disabled=user_disabled,
        )
        return result

    # Rule 1: Explicit user declaration → always scholarly
    if user_declared:
        confidence = 0.95
        if has_strong:
            confidence = min(0.95 + (len(strong) - 1) * 0.03, 1.0)
        # Soft exclusions can reduce confidence slightly but never negate
        if has_soft_exclusion:
            confidence = max(confidence - 0.10, 0.85)
        detected_type = _detect_type(frontmatter, body, identifiers)
        result = ScholarlyDetectionResult(
            is_scholarly=True,
            confidence=round(confidence, 2),
            reasons=reasons,
            identifiers=identifiers,
            detected_type=detected_type,
            strong_signals=strong,
            medium_signals=medium,
            hard_exclusion_signals=hard_exclusion,
            soft_exclusion_signals=soft_exclusion,
            user_declared=user_declared,
            user_disabled=user_disabled,
        )
        return result

    # Rule 2: Hard exclusion → not scholarly
    # (only applies when user has NOT explicitly declared it scholarly)
    if has_hard_exclusion:
        result = ScholarlyDetectionResult(
            is_scholarly=False,
            confidence=0.0,
            reasons=reasons,
            identifiers=identifiers,
            strong_signals=strong,
            medium_signals=medium,
            hard_exclusion_signals=hard_exclusion,
            soft_exclusion_signals=soft_exclusion,
            user_declared=user_declared,
            user_disabled=user_disabled,
        )
        return result

    # Rule 3: Strong signals → scholarly
    # Soft exclusions reduce confidence but do NOT negate strong signals
    if has_strong:
        confidence = min(0.90 + (len(strong) - 1) * 0.05, 1.0)
        confidence = min(confidence + len(medium) * 0.02, 1.0)
        # Soft exclusion: reduce confidence but keep is_scholarly=True
        if has_soft_exclusion:
            confidence = max(confidence - 0.15, 0.70)
            reasons.append("soft exclusion reduced confidence (strong signal present)")
        is_scholarly = True
    elif has_medium and len(medium) >= 2:
        # Multiple medium signals
        confidence = min(0.60 + len(medium) * 0.10, 0.89)
        # Soft exclusion can negate when only medium signals
        if has_soft_exclusion:
            confidence = max(confidence - 0.20, 0.40)
        is_scholarly = confidence >= 0.70
    elif has_medium and len(medium) == 1:
        confidence = 0.60
        if has_soft_exclusion:
            confidence = max(confidence - 0.20, 0.40)
        is_scholarly = confidence >= 0.60
    else:
        confidence = 0.0
        is_scholarly = False

    detected_type = _detect_type(frontmatter, body, identifiers)

    result = ScholarlyDetectionResult(
        is_scholarly=is_scholarly,
        confidence=round(confidence, 2),
        reasons=reasons,
        identifiers=identifiers,
        detected_type=detected_type,
        strong_signals=strong,
        medium_signals=medium,
        hard_exclusion_signals=hard_exclusion,
        soft_exclusion_signals=soft_exclusion,
        user_declared=user_declared,
        user_disabled=user_disabled,
    )
    return result


def _detect_type(
    frontmatter: Dict[str, Any],
    body: str,
    identifiers: Dict[str, str],
) -> str:
    """Detect the broad type of scholarly work."""
    fm_type = str(frontmatter.get("pub_type", frontmatter.get("type", ""))).lower()

    # Check frontmatter first
    if fm_type in ("journal-article", "article-journal", "journal_article"):
        return "article-journal"
    if fm_type in ("paper-conference", "conference", "proceedings-article"):
        return "paper-conference"
    if "thesis" in fm_type or "dissertation" in fm_type:
        return "thesis"
    if fm_type in ("preprint", "article"):
        return "preprint"
    if fm_type in ("book", "monograph"):
        return "book"
    if fm_type in ("chapter", "book-chapter"):
        return "chapter"
    if fm_type in ("report", "technical-report"):
        return "report"

    # Check identifier patterns (case-insensitive)
    arxiv_id = identifiers.get("arxiv_id", "").lower()
    if "arxiv" in arxiv_id:
        return "preprint"

    # Check body for structural clues
    if body:
        body_lower = body.lower()
        if any(kw in body_lower for kw in ("doctoral dissertation", "master's thesis", "ph.d. thesis")):
            return "thesis"
        if "conference" in body_lower and "proceedings" in body_lower:
            return "paper-conference"

    return "article-journal"  # Default assumption for scholarly works


def should_auto_enrich(result: ScholarlyDetectionResult, threshold: float = 0.90) -> bool:
    """Determine if auto-enrichment should proceed based on detection result.

    Rules:
      - User disabled → never
      - User declared (type: literature, scholarly.detected) → always
      - confidence >= threshold AND at least one strong signal → auto-enrich
      - Otherwise → skip auto-enrichment

    Args:
        result: Detection result to evaluate.
        threshold: Minimum confidence threshold (default 0.90).
    """
    if result.user_disabled:
        return False
    if result.user_declared:
        return True
    if not result.is_scholarly:
        return False
    if result.confidence < threshold:
        return False
    if not result.strong_signals:
        return False
    return True
