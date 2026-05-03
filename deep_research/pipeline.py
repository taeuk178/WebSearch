from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .models import (
    Evidence,
    RankedSource,
    ResearchBundle,
    ResearchPlan,
    ResearchQuestion,
    SearchQuery,
    SearchResult,
    Stage,
    StageEvent,
)
from .reader import PageReader, SnippetReader
from .safety import SafetyAssessment, assess_safety
from .search import MockSearchProvider, SearchProvider
from .writer import AnswerWriter, EvidenceAnswerWriter

EventHandler = Callable[[StageEvent], None]


class DeepResearchPipeline:
    def __init__(
        self,
        search_provider: SearchProvider | None = None,
        page_reader: PageReader | None = None,
        answer_writer: AnswerWriter | None = None,
        on_event: EventHandler | None = None,
    ):
        self.search_provider = search_provider or MockSearchProvider()
        self.page_reader = page_reader or SnippetReader()
        self.answer_writer = answer_writer or EvidenceAnswerWriter()
        self.on_event = on_event

    def run(self, user_query: str) -> ResearchBundle:
        question = self._queued(user_query)
        safety = assess_safety(question)
        plan = self._planning(question)
        initial_queries = self._initial_queries(question, plan)
        search_results = self._searching(initial_queries)
        evidence = self._reading(search_results, plan)
        self._ranking(search_results, question)
        follow_up_queries = self._follow_up_queries(question, plan, evidence)
        gap_results = self._searching_outline_gaps(follow_up_queries, existing_results=search_results)
        gap_evidence = self._reading(gap_results, plan)
        memory = self._evidence_memory([*evidence, *gap_evidence])
        final_outline = self._dynamic_outline(plan, memory)
        bundle = self._preparing_bundle(
            question=question,
            plan=plan,
            initial_queries=initial_queries,
            follow_up_queries=follow_up_queries,
            ranked_sources=self._ranking([*search_results, *gap_results], question),
            evidence=[*evidence, *gap_evidence],
            final_outline=final_outline,
            safety=safety,
        )
        self._completed(bundle)
        return bundle

    def _queued(self, user_query: str) -> ResearchQuestion:
        normalized = " ".join(user_query.strip().split())
        question = ResearchQuestion(
            raw=user_query,
            normalized=normalized,
            intent="learning_plan" if self._contains_any(normalized, ["공부", "학습", "study", "learn"]) else "research_answer",
            domain="medical_neuroscience" if self._contains_any(normalized, ["의료 신경과학", "neuroscience", "신경"]) else "general",
            risk_level="medium" if self._contains_any(normalized, ["의료", "medical", "clinical"]) else "low",
            output_format="roadmap" if self._contains_any(normalized, ["방법", "로드맵", "plan", "how"]) else "briefing",
        )
        self._emit(Stage.QUEUED, "질문을 작업 큐에 등록했습니다.", asdict(question))
        return question

    def _planning(self, question: ResearchQuestion) -> ResearchPlan:
        if question.domain == "medical_neuroscience":
            plan = ResearchPlan(
                main_question="의료 신경과학을 어떤 순서와 방식으로 공부해야 하는가?",
                subquestions=[
                    "어떤 선수지식이 필요한가?",
                    "신경해부학, 신경생리학, 시스템 신경과학, 임상 신경학은 어떤 순서로 배워야 하는가?",
                    "일반 학습자, 의대생, 연구자 지망생의 경로는 어떻게 달라지는가?",
                    "어떤 자료와 실습 방식이 효과적인가?",
                    "3개월 학습 로드맵으로 만들면 어떻게 되는가?",
                ],
                outline=[
                    "목표 설정",
                    "선수지식",
                    "핵심 학습 순서",
                    "추천 자료",
                    "공부 루틴",
                    "3개월 로드맵",
                    "주의할 점",
                ],
                assumptions=["사용자의 현재 수준이 명시되지 않아 초급-중급 전환자를 기준으로 답변합니다."],
            )
        else:
            plan = ResearchPlan(
                main_question=question.normalized,
                subquestions=["핵심 개념은 무엇인가?", "실행 순서는 무엇인가?", "주의할 점은 무엇인가?"],
                outline=["요약", "핵심 개념", "실행 방법", "주의할 점"],
                assumptions=["사용자의 배경지식이 명시되지 않아 일반 독자를 기준으로 답변합니다."],
            )
        self._emit(Stage.PLANNING, "리서치 계획과 초기 목차를 만들었습니다.", asdict(plan))
        return plan

    def _initial_queries(self, question: ResearchQuestion, plan: ResearchPlan) -> list[SearchQuery]:
        if question.domain == "medical_neuroscience":
            queries = [
                SearchQuery("medical neuroscience curriculum", "표준 커리큘럼 확인", 1),
                SearchQuery("neuroanatomy learning objectives medical students", "신경해부학 선수/목표 확인", 1),
                SearchQuery("clinical neuroscience case based learning", "임상 적용 학습 방식 확인", 2),
                SearchQuery("principles of neural science textbook study", "교재와 고급 학습 범위 확인", 3),
            ]
        else:
            queries = [SearchQuery(plan.main_question, "질문 전반의 배경 검색", 1)]
        self._emit(Stage.INITIAL_QUERIES, "초기 검색 쿼리를 생성했습니다.", {"queries": [asdict(q) for q in queries]})
        return queries

    def _searching(self, queries: Iterable[SearchQuery]) -> list[SearchResult]:
        raw_results = self.search_provider.search(queries, limit_per_query=4)
        results = self._dedupe_results(raw_results)
        self._emit(
            Stage.SEARCHING,
            "검색 결과를 수집했습니다.",
            {"result_count": len(results), "raw_result_count": len(raw_results)},
        )
        return results

    def _reading(self, results: Iterable[SearchResult], plan: ResearchPlan) -> list[Evidence]:
        evidence: list[Evidence] = []
        documents = self.page_reader.read(results)
        for document in documents:
            result = document.result
            chunks = document.chunks or [document.text]
            for chunk_index, chunk in enumerate(chunks[:3]):
                section = self._match_outline_section(chunk, plan.outline)
                claim = self._claim_from_result(result, chunk)
                evidence.append(
                    Evidence(
                        source_id=result.source_id,
                        claim=claim,
                        summary=self._evidence_summary(chunk),
                        confidence=self._confidence_for_source_type(result.source_type),
                        outline_section=section,
                        chunk_index=chunk_index,
                    )
                )
        self._emit(
            Stage.READING,
            "문서를 읽고 주장별 근거를 추출했습니다.",
            {
                "evidence_count": len(evidence),
                "page_read_count": sum(1 for item in documents if item.from_page),
                "chunk_count": sum(len(item.chunks or [item.text]) for item in documents),
            },
        )
        return evidence

    def _ranking(self, results: Iterable[SearchResult], question: ResearchQuestion) -> list[RankedSource]:
        ranked = [
            RankedSource(
                result=result,
                relevance=self._relevance(result, question),
                trust=self._trust(result.source_type),
                freshness=self._freshness(result.published_at),
            )
            for result in results
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        self._emit(
            Stage.RANKING,
            "출처를 관련성, 신뢰도, 최신성 기준으로 정렬했습니다.",
            {"sources": [{"source_id": item.result.source_id, "score": item.score} for item in ranked]},
        )
        return ranked

    def _follow_up_queries(
        self, question: ResearchQuestion, plan: ResearchPlan, evidence: list[Evidence]
    ) -> list[SearchQuery]:
        gaps = self._find_outline_gaps(plan, evidence)
        queries = [SearchQuery(self._query_for_gap(gap, question), f"목차 공백 보완: {gap}", 2) for gap in gaps[:3]]
        self._emit(
            Stage.FOLLOW_UP_QUERIES,
            "근거가 부족한 목차를 기준으로 후속 쿼리를 만들었습니다.",
            {"gaps": gaps, "queries": [asdict(q) for q in queries]},
        )
        return queries

    def _searching_outline_gaps(
        self, queries: Iterable[SearchQuery], existing_results: Iterable[SearchResult] = ()
    ) -> list[SearchResult]:
        raw_results = self.search_provider.search(queries, limit_per_query=2)
        results = self._dedupe_results(raw_results, existing_results=existing_results)
        self._emit(
            Stage.SEARCHING_OUTLINE_GAPS,
            "목차 공백 보완 검색을 수행했습니다.",
            {"result_count": len(results), "raw_result_count": len(raw_results)},
        )
        return results

    def _evidence_memory(self, evidence: list[Evidence]) -> dict[str, list[Evidence]]:
        memory: dict[str, list[Evidence]] = defaultdict(list)
        for item in evidence:
            memory[item.outline_section].append(item)
        self._emit(
            Stage.EVIDENCE_MEMORY,
            "근거를 목차 섹션별 메모리에 저장했습니다.",
            {"sections": {section: len(items) for section, items in memory.items()}},
        )
        return dict(memory)

    def _dynamic_outline(self, plan: ResearchPlan, memory: dict[str, list[Evidence]]) -> list[str]:
        final_outline = [section for section in plan.outline if section in memory]
        for section in plan.outline:
            if section not in final_outline:
                final_outline.append(section)
        self._emit(Stage.DYNAMIC_OUTLINE, "근거 커버리지에 맞춰 최종 목차를 재정렬했습니다.", {"outline": final_outline})
        return final_outline

    def _preparing_bundle(
        self,
        question: ResearchQuestion,
        plan: ResearchPlan,
        initial_queries: list[SearchQuery],
        follow_up_queries: list[SearchQuery],
        ranked_sources: list[RankedSource],
        evidence: list[Evidence],
        final_outline: list[str],
        safety: SafetyAssessment,
    ) -> ResearchBundle:
        limitations = [*plan.assumptions, *safety.notes]
        filtered_sources = [source for source in ranked_sources if source.trust >= safety.min_trust]
        if not filtered_sources:
            filtered_sources = ranked_sources
        answer = self.answer_writer.write(question, final_outline, evidence, filtered_sources, limitations)
        bundle = ResearchBundle(
            question=question,
            plan=plan,
            initial_queries=initial_queries,
            follow_up_queries=follow_up_queries,
            ranked_sources=filtered_sources,
            evidence=evidence,
            final_outline=final_outline,
            answer=answer,
            limitations=limitations,
            metadata={"generated_at": datetime.now(UTC).isoformat(), "safety_risk_level": safety.risk_level},
        )
        self._emit(Stage.PREPARING_BUNDLE, "최종 답변, 출처, 근거 맵을 하나의 번들로 묶었습니다.")
        return bundle

    def _completed(self, bundle: ResearchBundle) -> None:
        self._emit(Stage.COMPLETED, "딥 리서치 작업이 완료되었습니다.", {"source_count": len(bundle.ranked_sources)})

    def _match_outline_section(self, text: str, outline: list[str]) -> str:
        lower = text.lower()
        if any(term in lower for term in ["curriculum", "sequence", "covering"]):
            return "핵심 학습 순서" if "핵심 학습 순서" in outline else outline[0]
        if any(term in lower for term in ["anatomy", "pathway", "cranial"]):
            return "선수지식" if "선수지식" in outline else outline[0]
        if any(term in lower for term in ["textbook", "reference", "course"]):
            return "추천 자료" if "추천 자료" in outline else outline[0]
        if any(term in lower for term in ["case", "practice", "apply"]):
            return "공부 루틴" if "공부 루틴" in outline else outline[0]
        return outline[0]

    def _claim_from_result(self, result: SearchResult, text: str = "") -> str:
        lower = text.lower()
        if any(term in lower for term in ["mistake", "pitfall", "reliable sources", "주의"]):
            return "신경과학 학습에서는 암기 위주 접근과 출처가 약한 임상 주장을 경계해야 한다."
        if any(term in lower for term in ["twelve week", "12 week", "spaced review", "3개월"]):
            return "학습 계획은 주차별 순서와 반복 복습 체크포인트를 포함해야 한다."
        if result.source_type == "university_course":
            return "의료 신경과학은 체계적인 과목 순서와 학습 목표를 따라 공부해야 한다."
        if result.source_type == "textbook":
            return "고급 단계에서는 표준 신경과학 교재로 세포, 시스템, 행동, 임상 연결을 확장할 수 있다."
        if result.source_type == "medical_education":
            return "임상 케이스 기반 학습은 신경해부학과 신경생리학을 실제 판단으로 연결하는 데 유용하다."
        return "학습 계획은 목표, 선수지식, 복습 루틴, 점검 지표를 포함해야 한다."

    def _query_for_gap(self, gap: str, question: ResearchQuestion) -> str:
        mapping = {
            "목표 설정": "how to choose neuroscience learning goals",
            "선수지식": "prerequisites for medical neuroscience course",
            "3개월 로드맵": "medical neuroscience 12 week study plan",
            "주의할 점": "common mistakes studying neuroanatomy neuroscience",
        }
        if question.domain == "medical_neuroscience":
            return mapping.get(gap, f"medical neuroscience {gap}")
        return f"{question.normalized} {gap}"

    def _relevance(self, result: SearchResult, question: ResearchQuestion) -> float:
        haystack = f"{result.title} {result.snippet}".lower()
        if question.domain == "medical_neuroscience" and ("neuro" in haystack or "신경" in haystack):
            return 0.95
        return 0.65

    def _trust(self, source_type: str) -> float:
        return {
            "government_health": 0.96,
            "university_course": 0.95,
            "medical_education": 0.88,
            "textbook": 0.82,
            "education": 0.72,
            "technology": 0.74,
            "business": 0.7,
            "web": 0.6,
        }.get(source_type, 0.5)

    def _freshness(self, published_at: str | None) -> float:
        if not published_at:
            return 0.5
        try:
            year = int(published_at[:4])
        except ValueError:
            return 0.5
        current_year = datetime.now().year
        return max(0.35, min(1.0, 1.0 - ((current_year - year) * 0.08)))

    def _confidence_for_source_type(self, source_type: str) -> float:
        return round((self._trust(source_type) * 0.7) + 0.2, 2)

    def _evidence_summary(self, text: str, max_chars: int = 420) -> str:
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars].rstrip()}..."

    def _dedupe_results(
        self, results: Iterable[SearchResult], existing_results: Iterable[SearchResult] = ()
    ) -> list[SearchResult]:
        seen = {_canonical_url(result.url) for result in existing_results}
        seen_fingerprints = {_source_fingerprint(result) for result in existing_results}
        deduped: list[SearchResult] = []
        for result in results:
            key = _canonical_url(result.url)
            fingerprint = _source_fingerprint(result)
            if key in seen or fingerprint in seen_fingerprints:
                continue
            seen.add(key)
            seen_fingerprints.add(fingerprint)
            deduped.append(result)
        return deduped

    def _find_outline_gaps(self, plan: ResearchPlan, evidence: list[Evidence]) -> list[str]:
        counts: dict[str, int] = defaultdict(int)
        source_types: dict[str, set[str]] = defaultdict(set)
        for item in evidence:
            counts[item.outline_section] += 1
        gaps: list[str] = []
        for section in plan.outline:
            if counts[section] == 0:
                gaps.append(section)
            elif counts[section] < 2 and section in {"주의할 점", "3개월 로드맵", "추천 자료"}:
                gaps.append(section)
        for section in plan.outline:
            if section in gaps:
                continue
            matching_source_ids = {item.source_id for item in evidence if item.outline_section == section}
            if len(matching_source_ids) < 2 and section in {"핵심 학습 순서", "선수지식"}:
                gaps.append(section)
        return gaps

    def _emit(self, stage: Stage, message: str, payload: dict[str, Any] | None = None) -> None:
        event = StageEvent(stage=stage, message=message, payload=payload or {})
        if self.on_event:
            self.on_event(event)

    @staticmethod
    def _contains_any(text: str, keywords: list[str]) -> bool:
        lower = text.lower()
        return any(keyword.lower() in lower for keyword in keywords)


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), host, path, "", query, ""))


def _source_fingerprint(result: SearchResult) -> str:
    words = f"{result.title} {result.snippet}".lower().split()
    normalized = [word.strip(".,;:!?()[]{}") for word in words]
    important = [word for word in normalized if len(word) > 4]
    return " ".join(sorted(set(important))[:12])
