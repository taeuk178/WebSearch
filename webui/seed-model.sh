#!/bin/bash
# Open WebUI에 Qwen3.6 모델 설정을 시드한다.
# MLX 연결 모델(id = 모델 절대경로)을 워크스페이스 설정으로 "오버라이드"하여:
#   - 표시명을 "Qwen3.6 35B" 로 (로컬 경로를 사용자에게 숨김)
#   - function_calling=legacy 로 고정 (Legacy 웹 검색 트리거에 필수)
#   - 기본 언어 한국어 시스템 프롬프트 주입 (CLAUDE.md 같은 파일은 없음 → 시스템 프롬프트가 그 역할)
#   - max_tokens 여유 확보 (Qwen3.6 thinking 토큰 소비 대비)
#
# 사전조건: run-model-server.sh + run-webui.sh 로 두 서버가 떠 있고, 관리자 API 토큰 필요.
#   OWUI_TOKEN=<관리자 토큰> ./seed-model.sh
# 관리자 토큰: Open WebUI > 설정 > 계정 > API 키.
set -euo pipefail

BASE="${OWUI_BASE:-http://127.0.0.1:3000}"
TOKEN="${OWUI_TOKEN:?관리자 API 토큰을 OWUI_TOKEN 으로 전달하세요 (설정 > 계정 > API 키)}"
# MLX 서버에 넘긴 모델 경로 = Open WebUI가 보는 연결 모델 id 와 동일해야 한다.
BASE_MODEL="${BASE_MODEL:-$HOME/gemma-server/models/Qwen3.6-35B-A3B-4bit}"
DISPLAY_NAME="${DISPLAY_NAME:-Qwen3.6 35B}"
# 출력 상한. Qwen3.6 은 thinking 모델이라 추론이 이 예산에서 먼저 소비된다.
# 너무 작으면(예: 2048) 추론 도중 예산이 끝나 finish_reason=length 로 최종 답변이
# 통째로 비어버린다. 웹 검색 스니펫 5개를 요약하는 경우까지 감안해 8192 로 잡는다.
MAX_TOKENS="${MAX_TOKENS:-8192}"

read -r -d '' SYS_PROMPT <<'PROMPT' || true
당신은 한국어 사용자를 위한 로컬 웹 검색 어시스턴트입니다. 사용자가 다른 언어를 명시적으로 요청하지 않는 한 항상 한국어로 답하세요.
중요: 내부 추론(생각)은 최대한 짧게 하세요. 추론과 최종 답변이 같은 출력 예산을 나눠 쓰기 때문에, 추론이 길어지면 최종 답변이 잘립니다. 간단한 질문에는 거의 추론하지 말고 바로 답하세요.
어떤 대상을 확실히 알지 못하면 추측을 반복하지 말고 "정확히 알지 못한다"고 인정한 뒤 웹 검색을 권하고 즉시 최종 답변으로 넘어가세요.
웹 검색 결과가 제공되면 근거가 된 출처를 인용 번호로 함께 제시하고, 검색 결과가 부족하거나 출처가 서로 상충하면 그 사실을 분명히 밝히고 확정적으로 단정하지 마세요.
추론만 출력하지 말고 반드시 한국어 최종 답변을 작성하세요.
PROMPT

python3 - "$BASE" "$TOKEN" "$BASE_MODEL" "$DISPLAY_NAME" "$MAX_TOKENS" "$SYS_PROMPT" <<'PY'
import sys, json, urllib.request, urllib.parse
base, token, base_model, name, max_tokens, sysp = sys.argv[1:7]
H={"Authorization":f"Bearer {token}","Content-Type":"application/json"}
payload={
  "id": base_model,                # 연결 모델 id를 그대로 오버라이드 (별도 프록시 모델 만들지 않음)
  "base_model_id": None,
  "name": name,
  "meta": {"description": "Qwen3.6 35B-A3B (MLX) 로컬 · 한국어 기본 · Legacy 웹 검색",
           "capabilities": {"web_search": True}},
  # Qwen3.6 권장 샘플링(temp 1.0 / top_p 0.95). top_k=20 은 Open WebUI가 OpenAI
  # 백엔드로 전달하지 않으므로 run-model-server.sh 에서 서버 기본값으로 박는다.
  "params": {"function_calling":"legacy","max_tokens":int(max_tokens),"temperature":1.0,"top_p":0.95,"system":sysp},
  "access_grants": [],
  "is_active": True,
}
def call(path):
    req=urllib.request.Request(base+path, data=json.dumps(payload).encode(), headers=H)
    return urllib.request.urlopen(req).read().decode()
# 신규면 create, 이미 있으면 update 로 폴백
try:
    call("/api/v1/models/create"); print(f"생성: {name} (id={base_model})")
except urllib.error.HTTPError:
    call("/api/v1/models/model/update?id="+urllib.parse.quote(base_model, safe=""))
    print(f"갱신: {name} (id={base_model})")
print("function_calling=legacy, 한국어 기본 시스템 프롬프트 적용됨")
# 웹 검색은 강제하지 않는다. 필요할 때 입력창 웹 검색 토글로 켠다(on-demand).
PY
