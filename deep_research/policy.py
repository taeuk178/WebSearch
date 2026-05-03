from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


ARXIV_REQUEST_INTERVAL_SECONDS = 3.5


@dataclass
class RateLimiter:
    min_interval_seconds: float
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep
    _last_request_at: float | None = field(default=None, init=False)

    def wait(self) -> float:
        now = self.clock()
        if self._last_request_at is None:
            self._last_request_at = now
            return 0.0
        wait_seconds = max(0.0, self.min_interval_seconds - (now - self._last_request_at))
        if wait_seconds:
            self.sleeper(wait_seconds)
            now = self.clock()
        self._last_request_at = now
        return wait_seconds


def execution_cautions(*, includes_arxiv: bool = False, high_stakes: bool = False) -> list[str]:
    cautions = [
        "검색 API와 원문 페이지 fetch는 provider별 rate limit, timeout, 실패 폴백을 고려해야 합니다.",
        "검색 결과 snippet만으로 작성한 근거는 원문 읽기 결과보다 신뢰도가 낮을 수 있습니다.",
        "중복 제거는 canonical URL과 간단한 fingerprint 기준이므로 의미상 중복 문서가 남을 수 있습니다.",
    ]
    if includes_arxiv:
        cautions.append("arXiv 논문 또는 API 조회는 각 요청 사이에 최소 3.5초 간격을 둡니다.")
    if high_stakes:
        cautions.append("의료, 법률, 금융 주제는 고신뢰 출처를 우선하고 개인별 처방형 결론을 피해야 합니다.")
    return cautions
