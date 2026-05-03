from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Stage(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    INITIAL_QUERIES = "initial_queries"
    SEARCHING = "searching"
    READING = "reading"
    RANKING = "ranking"
    FOLLOW_UP_QUERIES = "follow_up_queries"
    SEARCHING_OUTLINE_GAPS = "searching_outline_gaps"
    EVIDENCE_MEMORY = "evidence_memory"
    DYNAMIC_OUTLINE = "dynamic_outline"
    PREPARING_BUNDLE = "preparing_bundle"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ResearchQuestion:
    raw: str
    normalized: str
    intent: str
    domain: str
    risk_level: str
    output_format: str
    language: str = "ko"


@dataclass(frozen=True)
class ResearchPlan:
    main_question: str
    subquestions: list[str]
    outline: list[str]
    assumptions: list[str]


@dataclass(frozen=True)
class SearchQuery:
    text: str
    purpose: str
    priority: int = 1


@dataclass(frozen=True)
class SearchResult:
    source_id: str
    title: str
    url: str
    snippet: str
    source_type: str
    query: str
    published_at: str | None = None


@dataclass(frozen=True)
class Evidence:
    source_id: str
    claim: str
    summary: str
    confidence: float
    outline_section: str
    chunk_index: int = 0


@dataclass(frozen=True)
class RankedSource:
    result: SearchResult
    relevance: float
    trust: float
    freshness: float

    @property
    def score(self) -> float:
        return round((self.relevance * 0.5) + (self.trust * 0.35) + (self.freshness * 0.15), 3)


@dataclass(frozen=True)
class ResearchBundle:
    question: ResearchQuestion
    plan: ResearchPlan
    initial_queries: list[SearchQuery]
    follow_up_queries: list[SearchQuery]
    ranked_sources: list[RankedSource]
    evidence: list[Evidence]
    final_outline: list[str]
    answer: str
    limitations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StageEvent:
    stage: Stage
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
