#!/bin/bash
# Open WebUI에 gemma-4 모델 설정을 시드한다.
# MLX 연결 모델(id = 모델 절대경로)을 워크스페이스 설정으로 "오버라이드"하여:
#   - 표시명을 "gemma4 26b" 로 (로컬 경로를 사용자에게 숨김)
#   - function_calling=legacy 로 고정 (Legacy 웹 검색 트리거에 필수)
#   - 기본 언어 한국어 시스템 프롬프트 주입 (CLAUDE.md 같은 파일은 없음 → 시스템 프롬프트가 그 역할)
#   - max_tokens 여유 확보 (gemma-4 thinking 채널 대비)
#
# 사전조건: run-model-server.sh + run-webui.sh 로 두 서버가 떠 있고, 관리자 API 토큰 필요.
#   OWUI_TOKEN=<관리자 토큰> ./seed-model.sh
# 관리자 토큰: Open WebUI > 설정 > 계정 > API 키.
set -euo pipefail

BASE="${OWUI_BASE:-http://127.0.0.1:3000}"
TOKEN="${OWUI_TOKEN:?관리자 API 토큰을 OWUI_TOKEN 으로 전달하세요 (설정 > 계정 > API 키)}"
# MLX 서버에 넘긴 모델 경로 = Open WebUI가 보는 연결 모델 id 와 동일해야 한다.
BASE_MODEL="${BASE_MODEL:-$HOME/gemma-server/models/gemma-4-26b-a4b-it-4bit}"
DISPLAY_NAME="${DISPLAY_NAME:-gemma4 26b}"
# 출력 상한. 너무 크면(예: 33000) 사고 채널이 반복 루프에 빠질 때 그 반복이
# 상한까지 그대로 길어져 "벽 같은 반복"이 된다. 4096 이면 정상 답변에 충분하고 최악도 짧게 제한.
MAX_TOKENS="${MAX_TOKENS:-4096}"

read -r -d '' SYS_PROMPT <<'PROMPT' || true
당신은 한국어 사용자를 위한 로컬 웹 검색 어시스턴트입니다. 사용자가 다른 언어를 명시적으로 요청하지 않는 한 항상 한국어로 답하세요.
중요: 내부 추론(생각)은 짧게 하세요. 같은 문장이나 같은 추측을 절대 반복하지 마세요. 어떤 대상을 확실히 알지 못하면, 계속 추측을 반복하지 말고 "정확히 알지 못한다"고 인정한 뒤 웹 검색을 권하고 즉시 최종 답변으로 넘어가세요.
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
  "meta": {"description": "Gemma-4 26B (MLX) 로컬 · 한국어 기본 · Legacy 웹 검색",
           "capabilities": {"web_search": True}},
  # gemma-4 권장 샘플링(temp 1.0 / top_p 0.95). 낮은 temp는 thinking 채널이 반복 루프에 빠진다.
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

# 웹 검색 "항상 켜기"(사용자 설정 ui.webSearch="always"). UI 토글 표시용.
req=urllib.request.Request(base+"/api/v1/users/user/settings/update",
    data=json.dumps({"ui":{"webSearch":"always"}}).encode(), headers=H)
urllib.request.urlopen(req).read()
print("웹 검색 항상 켜기(always) 설정됨")

# 전역 Filter 'force_web_search': UI 토글과 무관하게 매 요청에 웹 검색을 서버에서 강제.
import os, time
fn_path = os.path.join(os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else '.', 'functions', 'force_web_search.py')
try:
    fn_content = open(fn_path, encoding='utf-8').read()
except Exception:
    fn_content = None
if fn_content:
    now=int(time.time())
    body=json.dumps({"id":"force_web_search","name":"Force Web Search","type":"filter",
        "content":fn_content,"meta":{"description":"모든 요청에 웹 검색 강제","manifest":{}},
        "is_active":True,"is_global":True,"updated_at":now,"created_at":now}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(base+"/api/v1/functions/create", data=body, headers=H)).read()
    except urllib.error.HTTPError:
        urllib.request.urlopen(urllib.request.Request(base+"/api/v1/functions/id/force_web_search/update", data=body, headers=H)).read()
    # 활성 + 전역 보장 (현재 상태가 꺼져 있으면 토글)
    def toggle(p):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(base+p, data=b"{}", headers=H)).read())
        except Exception: return {}
    cur=json.loads(urllib.request.urlopen(urllib.request.Request(base+"/api/v1/functions/id/force_web_search", headers=H)).read())
    if not cur.get("is_active"):  toggle("/api/v1/functions/id/force_web_search/toggle")
    if not cur.get("is_global"): toggle("/api/v1/functions/id/force_web_search/toggle/global")
    print("전역 필터 force_web_search 활성화됨 (토글 무관 강제 검색)")
PY
