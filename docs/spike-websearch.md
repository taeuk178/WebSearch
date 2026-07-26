# 웹 검색 호환성 스파이크 결과

request의 핵심 검증 항목("Open WebUI 웹 검색이 MLX gemma-4와 함께 동작하는가")에 대한
실측 결과다. **결론: 통과(PASS).** request가 지정한 Legacy 웹 검색 + bypass 플래그
경로가 그대로 동작하며, 별도 상태 없는 검색 연동 계층(대안)을 구현할 필요가 없다.

## 검증 환경 (고정 버전)

| 구성요소 | 버전 |
|---|---|
| 하드웨어 | Apple M4, 통합 메모리 32GB (Mac mini) |
| macOS | 26.2 (25C56) |
| 모델 | `mlx-community/gemma-4-26b-a4b-it-4bit` (`gemma4`, MoE 128 experts, 4bit) |
| mlx-lm | 0.31.3 (mlx 0.32.0) |
| open-webui | 0.10.2 |
| Python | 서버 3.12 (mlx), WebUI 3.11 (uv 네이티브) |

> 실제 하드웨어 메모리는 32GB로 확인됨(request 문서에는 36GB로 기재). 동작에는 영향 없음.

## 1. MLX 모델 서빙 — 통과

- `mlx_lm 0.31.3`에 `gemma4` / `gemma4_text` 구현이 포함되어 로컬 모델이 정상 로드·생성됨.
- `python -m mlx_lm server`가 OpenAI 호환 `/v1/chat/completions` 제공, `127.0.0.1`에만 바인딩.
- Peak memory ≈ 14.3GB, 생성 ≈ 40 tok/s.
- 이 모델은 `<|channel>thought` 형태의 **사고(thinking) 채널**을 사용한다.
  mlx-lm 서버가 이를 자동 파싱하여 최종 답변은 `message.content`,
  사고 과정은 `message.reasoning` 필드로 분리한다. (Open WebUI의 reasoning 표시와 호환)

## 2. Open WebUI 웹 검색 — 통과

`open_webui/routers/retrieval.py`의 `process_web_search` 및
`open_webui/utils/middleware.py`의 분기를 코드로 확인 후 실측했다.

### 두 bypass 플래그의 실제 동작 (코드 확인)

- `BYPASS_WEB_SEARCH_WEB_LOADER=True`
  → `get_web_loader`(전체 페이지 수집)를 **호출하지 않고**, 각 검색 결과의
  `snippet`만으로 문서를 만든다. metadata에 `title`/`link`/`snippet` 포함.
- `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=True`
  → `save_docs_to_vector_db`(임베딩·벡터화)를 **건너뛰고** 스니펫을 그대로
  모델 컨텍스트로 반환한다 (`collection_name: None`). 벡터 저장소를 만들지 않는다.

즉 request가 원한 "임베딩·벡터·전체페이지 수집 없이 제목·URL·스니펫만 모델에 직접 전달"이
**정확히 이 조합으로 구현된다.**

### ⚠️ 가장 중요한 운영 조건: `function_calling=legacy`

middleware의 강제 웹 검색은 다음 조건에서만 트리거된다:

```python
if 'web_search' in features and features['web_search']:
    if metadata.get('params', {}).get('function_calling') == 'legacy':
        form_data = await chat_web_search_handler(...)
```

- 모델 파라미터 `function_calling`의 기본값은 **native**이고, 이 경우 Open WebUI는
  모델이 스스로 `web_search` **도구를 호출**하기를 기대한다.
- MLX gemma-4는 Open WebUI 네이티브 도구 호출로 자동 검색하지 않으므로,
  **native 상태에서는 웹 검색이 아예 실행되지 않는다.** (실측: 검색 로그 없이 모델이
  "지식 컷오프" 답변만 반환)
- 해결: 모델의 기본 파라미터를 `function_calling=legacy`로 고정한다.
  → 이 저장소에서는 워크스페이스 모델 `mlx-community/gemma-4-26b-a4b-it-4bit`를
  `function_calling=legacy`, `max_tokens=2000`으로 등록하여 UI에서 파라미터 지정 없이
  동작하게 한다. (`webui/seed-model.sh` 참조)

### thinking 채널과 max_tokens

- gemma-4의 사고 채널이 토큰을 상당히 소비한다(측정: 검색 답변 1회 completion ≈ 1,782 tokens).
- `max_tokens`가 작으면 사고 도중 `finish_reason: length`로 잘려 **최종 답변이 비는** 현상 발생.
- 초기값 `max_tokens=2000`에서 정상적으로 `finish_reason: stop` + 인용 포함 답변 확인.
  메모리·지연 측정 후 조정한다.

## 3. 실측 결과 (end-to-end)

워크스페이스 모델 기본값(`function_calling=legacy`)만으로, API에 `features.web_search=true`만
지정하여 검증(UI 웹 검색 토글과 동일 경로):

- 질의 "MLX 프레임워크가 뭔지 웹에서 찾아…" →
  DuckDuckGo 검색 → 스니펫 주입 → `finish_reason: stop`,
  `sources` 반환(제목+URL, 클릭 가능한 출처), 본문에 `[1][2][6]…` 인용 표기.
- 질의 "오늘 기준 대한민국 대통령…" → 상충하는 출처(윤석열/이재명)를 모델이 **명시**하고
  확정적으로 단정하지 않음 → request의 "출처 충돌 시 단정 금지" 요건 충족.
- `sources` 없이 native로 호출하면 검색이 실행되지 않음(대조 확인).

### 관찰된 튜닝 포인트 (v1에서 조정 대상)

- `WEB_SEARCH_RESULT_COUNT=5`는 **검색어 1개당** 5개다. `ENABLE_SEARCH_QUERY_GENERATION`이
  켜져 있으면 모델이 여러 검색어를 만들어 총 결과가 5를 넘을 수 있다(실측 2쿼리×5=10).
  request의 "검색 한 번에 5개 이하"는 엔진 호출 기준으로는 충족. 총량을 엄격히 5로 제한하려면
  검색어 생성을 끄거나 쿼리 수를 제한한다(단, 추가 LLM 호출 1회가 사라져 지연도 감소).
- 비스트리밍 전체 응답 지연은 검색어 생성+검색+생성 포함 수십 초~2분대.
  request의 "첫 토큰 30초 목표"는 **스트리밍 기준**으로 별도 측정 필요.

## 채택한 검색 연동 방식

Open WebUI **내장 Legacy 웹 검색**을 그대로 사용한다. 별도 검색 프록시/연동 계층은
구현하지 않는다(스파이크 통과로 불필요). 확정 설정:

```
ENABLE_WEB_SEARCH=True
WEB_SEARCH_ENGINE=duckduckgo
WEB_SEARCH_RESULT_COUNT=5
BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=True
BYPASS_WEB_SEARCH_WEB_LOADER=True
```
+ 모델 파라미터 `function_calling=legacy` (필수).
