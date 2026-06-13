"""PKB Scholarly Metadata Enrichment — Phase 1A.

Academic metadata enhancement layer for PKB:
  - Identify literature → identify journal → match rankings → generate citations.

Phase 1A scope: backend foundation only.
  - No UI changes, no /pkb integration, no PostToolUse hook changes.
  - No JCR / Scopus / CAS-JCR commercial data sources.
"""

__version__ = "1.0.0a1"

from .models import (
    CacheStatus,
    CitationData,
    CitationEngine,
    CitationStyle,
    EnrichmentResult,
    JournalIdentity,
    JournalLevel,
    JournalRanking,
    MatchMethod,
    MatchResult,
    MetricSnapshot,
    ScholarlyRecord,
    SourceStatus,
)
