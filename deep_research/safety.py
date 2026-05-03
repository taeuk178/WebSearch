from __future__ import annotations

from dataclasses import dataclass

from .models import ResearchQuestion


@dataclass(frozen=True)
class SafetyAssessment:
    risk_level: str
    notes: list[str]
    min_trust: float


def assess_safety(question: ResearchQuestion) -> SafetyAssessment:
    text = question.normalized.lower()
    if any(term in text for term in ["진단", "치료", "처방", "diagnosis", "treatment", "prescription"]):
        return SafetyAssessment(
            risk_level="high",
            notes=[
                "의료 주제는 개인 진단이나 치료 지시가 아니라 학습 목적의 일반 정보로 제한합니다.",
                "의료 결정을 위해서는 자격 있는 의료 전문가와 확인해야 합니다.",
            ],
            min_trust=0.82,
        )
    if question.risk_level == "medium":
        return SafetyAssessment(
            risk_level="medium",
            notes=["의료 관련 학습 주제이므로 대학, 정부 보건기관, 의학교육 자료를 우선합니다."],
            min_trust=0.72,
        )
    return SafetyAssessment(risk_level="low", notes=[], min_trust=0.5)
