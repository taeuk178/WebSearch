from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .models import SearchQuery, SearchResult


class SearchProviderError(RuntimeError):
    """Raised when a search provider cannot return usable results."""


class SearchProvider(ABC):
    @abstractmethod
    def search(self, queries: Iterable[SearchQuery], limit_per_query: int = 5) -> list[SearchResult]:
        """Return search results for the provided queries."""


class MockSearchProvider(SearchProvider):
    """Deterministic provider used for local development and tests.

    Replace this with Tavily, Brave, Exa, Bing, or a custom crawler in production.
    The rest of the pipeline only depends on the SearchProvider interface.
    """

    def __init__(self) -> None:
        self._next_source_number = 1

    def search(self, queries: Iterable[SearchQuery], limit_per_query: int = 5) -> list[SearchResult]:
        results: list[SearchResult] = []
        for query in queries:
            fixtures = _fixtures_for_query(query.text)
            for item in fixtures[:limit_per_query]:
                source_id = f"S{self._next_source_number}"
                self._next_source_number += 1
                results.append(
                    SearchResult(
                        source_id=source_id,
                        title=item["title"],
                        url=item["url"],
                        snippet=item["snippet"],
                        source_type=item["source_type"],
                        published_at=item.get("published_at"),
                        query=query.text,
                    )
                )
        return results


class BraveSearchProvider(SearchProvider):
    """Brave Search API provider.

    This keeps the pipeline contract unchanged: callers still receive a flat
    list of SearchResult objects with stable local source IDs.
    """

    DEFAULT_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 10.0,
        country: str = "us",
        search_lang: str = "en",
        opener=urlopen,
    ) -> None:
        if not api_key:
            raise ValueError("Brave Search provider requires BRAVE_SEARCH_API_KEY or --brave-api-key.")
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout
        self.country = country
        self.search_lang = search_lang
        self._opener = opener
        self._next_source_number = 1

    def search(self, queries: Iterable[SearchQuery], limit_per_query: int = 5) -> list[SearchResult]:
        results: list[SearchResult] = []
        for query in queries:
            results.extend(self._search_one(query, limit_per_query))
        return results

    def _search_one(self, query: SearchQuery, limit_per_query: int) -> list[SearchResult]:
        params = urlencode(
            {
                "q": query.text,
                "count": max(1, min(limit_per_query, 20)),
                "country": self.country,
                "search_lang": self.search_lang,
            }
        )
        request = Request(
            f"{self.endpoint}?{params}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
                "User-Agent": "websearch-deep-research/0.1",
            },
        )

        try:
            with self._opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise SearchProviderError(f"Brave Search request failed with HTTP {exc.code}.") from exc
        except URLError as exc:
            raise SearchProviderError(f"Brave Search request failed: {exc.reason}.") from exc
        except json.JSONDecodeError as exc:
            raise SearchProviderError("Brave Search returned invalid JSON.") from exc

        raw_results = payload.get("web", {}).get("results", [])
        if not isinstance(raw_results, list):
            return []

        results: list[SearchResult] = []
        for item in raw_results[:limit_per_query]:
            if not isinstance(item, dict):
                continue
            title = _clean_text(item.get("title"))
            url = _clean_text(item.get("url"))
            snippet = _clean_text(item.get("description")) or title
            if not title or not url:
                continue
            results.append(
                SearchResult(
                    source_id=self._next_source_id(),
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_type=_infer_source_type(url, title, snippet),
                    published_at=_published_at_from_brave(item),
                    query=query.text,
                )
            )
        return results

    def _next_source_id(self) -> str:
        source_id = f"S{self._next_source_number}"
        self._next_source_number += 1
        return source_id


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def _published_at_from_brave(item: dict[str, object]) -> str | None:
    for key in ("page_age", "age"):
        value = _clean_text(item.get(key))
        if value:
            return value
    return None


def _infer_source_type(url: str, title: str, snippet: str) -> str:
    host = urlparse(url).hostname or ""
    haystack = f"{host} {title} {snippet}".lower()
    if host.endswith(".edu"):
        return "university_course"
    if any(domain in host for domain in ["nih.gov", "ncbi.nlm.nih.gov", "cdc.gov", "who.int"]):
        return "government_health"
    if any(term in haystack for term in ["textbook", "book", "principles of neural science"]):
        return "textbook"
    if any(term in haystack for term in ["medical", "clinical", "neurology", "neuroscience"]):
        return "medical_education"
    return "web"


def _fixtures_for_query(query: str) -> list[dict[str, str]]:
    lower = query.lower()
    if "ai" in lower or "에이전트" in lower or "automation" in lower or "자동화" in lower:
        if "주의" in lower or "risk" in lower or "mistake" in lower:
            return [
                {
                    "title": "AI Automation Risk Checklist",
                    "url": "https://example.com/ai-automation/risk-checklist",
                    "snippet": "AI automation rollouts should define human review, data access limits, audit logs, fallback paths, and quality checks before production use.",
                    "source_type": "technology",
                    "published_at": "2025",
                }
            ]
        return [
            {
                "title": "AI Agent Workflow Automation Guide",
                "url": "https://example.com/ai-agents/workflow-automation-guide",
                "snippet": "Teams can introduce AI agents by selecting repeatable workflows, defining tool permissions, measuring quality, and keeping humans in approval loops.",
                "source_type": "technology",
                "published_at": "2025",
            },
            {
                "title": "Enterprise Automation Operating Model",
                "url": "https://example.org/enterprise-automation/operating-model",
                "snippet": "Successful automation programs start with process inventory, task prioritization, ownership, monitoring, rollback, and governance checkpoints.",
                "source_type": "business",
                "published_at": "2024",
            },
            {
                "title": "AI Agent Evaluation Metrics",
                "url": "https://example.com/ai-agents/evaluation-metrics",
                "snippet": "Agent deployments should track task success rate, escalation rate, latency, cost, user satisfaction, and incidents by workflow.",
                "source_type": "technology",
                "published_at": "2025",
            },
        ]

    if "learning goals" in lower:
        return [
            {
                "title": "Setting Learning Goals for Neuroscience",
                "url": "https://example.edu/neuroscience/learning-goals",
                "snippet": "Learners should define whether their goal is medical school readiness, clinical localization, research literacy, or patient-care context.",
                "source_type": "university_course",
                "published_at": "2025",
            }
        ]

    if "12 week" in lower or "3개월" in lower:
        return [
            {
                "title": "Twelve Week Medical Neuroscience Study Plan",
                "url": "https://example.org/medical-neuroscience/12-week-study-plan",
                "snippet": "A twelve week plan can sequence foundations, neuroanatomy, physiology, systems neuroscience, clinical cases, and spaced review checkpoints.",
                "source_type": "medical_education",
                "published_at": "2025",
            }
        ]

    if "common mistakes" in lower or ("주의" in lower and ("neuro" in lower or "신경" in lower)):
        return [
            {
                "title": "Common Pitfalls in Neuroanatomy Study",
                "url": "https://example.org/neuroanatomy/common-pitfalls",
                "snippet": "Common mistakes include memorizing pathways without function, skipping lesion localization practice, and using clinical claims without reliable sources.",
                "source_type": "medical_education",
                "published_at": "2024",
            }
        ]

    if "neuro" in lower or "신경" in lower:
        return [
            {
                "title": "Medical Neuroscience Course Outline",
                "url": "https://example.edu/medical-neuroscience/course-outline",
                "snippet": "A medical neuroscience course sequence covering neuroanatomy, neural signaling, sensory and motor systems, and clinical localization.",
                "source_type": "university_course",
                "published_at": "2025",
            },
            {
                "title": "Neuroanatomy Learning Objectives for Medical Students",
                "url": "https://example.edu/neuroanatomy/learning-objectives",
                "snippet": "Students should connect brain, spinal cord, cranial nerve, and pathway anatomy to neurological examination findings and lesion localization.",
                "source_type": "university_course",
                "published_at": "2024",
            },
            {
                "title": "Principles of Neural Science Reference",
                "url": "https://example.com/books/principles-of-neural-science",
                "snippet": "A comprehensive reference for cellular neuroscience, systems neuroscience, development, plasticity, behavior, and clinical connections.",
                "source_type": "textbook",
                "published_at": "2021",
            },
            {
                "title": "Clinical Neurology Case-Based Learning",
                "url": "https://example.org/clinical-neurology/cases",
                "snippet": "Case-based practice helps learners apply neuroanatomy and neurophysiology to stroke, epilepsy, movement disorders, and neuropathy.",
                "source_type": "medical_education",
                "published_at": "2025",
            },
        ]

    return [
        {
            "title": "Learning Roadmap Template",
            "url": "https://example.com/learning-roadmap",
            "snippet": "Effective study plans define goals, prerequisites, core sequence, active recall, spaced repetition, projects, and checkpoints.",
            "source_type": "education",
            "published_at": "2025",
        }
    ]
