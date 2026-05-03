from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Evidence, RankedSource, ResearchQuestion


class AnswerWriter(ABC):
    @abstractmethod
    def write(
        self,
        question: ResearchQuestion,
        final_outline: list[str],
        evidence: list[Evidence],
        ranked_sources: list[RankedSource],
        limitations: list[str],
    ) -> str:
        """Compose the final answer while preserving source IDs."""


class EvidenceAnswerWriter(AnswerWriter):
    """Deterministic writer that uses the same contract an LLM writer would use."""

    def write(
        self,
        question: ResearchQuestion,
        final_outline: list[str],
        evidence: list[Evidence],
        ranked_sources: list[RankedSource],
        limitations: list[str],
    ) -> str:
        if question.domain == "medical_neuroscience":
            return self._write_medical_neuroscience(final_outline, ranked_sources, limitations)
        return self._write_general(question, final_outline, evidence, ranked_sources, limitations)

    def _write_medical_neuroscience(
        self, final_outline: list[str], ranked_sources: list[RankedSource], limitations: list[str]
    ) -> str:
        source_ids = _top_source_ids(ranked_sources, 4)
        lines = [
            "의료 신경과학은 바로 논문이나 임상 질환부터 들어가기보다, 기초 생물학과 생리학을 정리한 뒤 신경해부학, 신경생리학, 시스템 신경과학, 임상 케이스 순서로 가는 편이 안정적입니다.",
            "",
            "추천 순서는 다음과 같습니다.",
            "1. 세포생물학, 일반생리학, 기본 해부학으로 선수지식을 잡습니다.",
            "2. 뇌, 척수, 말초신경, cranial nerve, 주요 pathway를 신경해부학으로 익힙니다.",
            "3. 활동전위, 시냅스, 감각계, 운동계, 자율신경계를 신경생리학과 시스템 신경과학으로 연결합니다.",
            "4. 마지막에는 stroke, epilepsy, Parkinson disease 같은 임상 케이스로 병변 위치와 증상을 연결해 봅니다.",
            "",
            "3개월 로드맵은 1개월차 기초 생리학과 신경해부학, 2개월차 신경생리학과 시스템 신경과학, 3개월차 임상 케이스와 반복 복습으로 구성하는 것이 좋습니다.",
            "",
            f"근거 출처: {', '.join(source_ids)}",
            f"사용한 최종 목차: {', '.join(final_outline)}",
        ]
        if limitations:
            lines.extend(["", f"제한사항: {' '.join(limitations)}"])
        return "\n".join(lines)

    def _write_general(
        self,
        question: ResearchQuestion,
        final_outline: list[str],
        evidence: list[Evidence],
        ranked_sources: list[RankedSource],
        limitations: list[str],
    ) -> str:
        source_ids = _top_source_ids(ranked_sources, 3)
        evidence_lines = [f"- {item.outline_section}: {item.summary} [{item.source_id}]" for item in evidence[:3]]
        lines = [
            f"{question.normalized}에 대한 근거 기반 요약입니다.",
            "",
            *evidence_lines,
            "",
            f"근거 출처: {', '.join(source_ids)}",
            f"사용한 최종 목차: {', '.join(final_outline)}",
        ]
        if limitations:
            lines.extend(["", f"제한사항: {' '.join(limitations)}"])
        return "\n".join(lines)


def _top_source_ids(ranked_sources: list[RankedSource], count: int) -> list[str]:
    return [item.result.source_id for item in ranked_sources[:count]]
