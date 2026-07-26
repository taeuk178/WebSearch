"""
title: Force Web Search
description: 모든 요청에 웹 검색을 강제로 켠다 (UI 토글과 무관). 웹 검색 전용 서버.
"""
from pydantic import BaseModel


class Filter:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__=None) -> dict:
        # features.web_search 를 강제로 True 로. 미들웨어가 features 를 읽기 전(inlet)에 실행된다.
        features = body.get("features")
        if not isinstance(features, dict):
            features = {}
        features["web_search"] = True
        body["features"] = features
        return body
