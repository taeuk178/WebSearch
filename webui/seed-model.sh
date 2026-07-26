#!/bin/bash
# Open WebUI에 gemma-4 워크스페이스 모델을 등록한다.
#  - 표시명을 mlx-community/gemma-4-26b-a4b-it-4bit 로 고정
#  - function_calling=legacy 로 고정 (Legacy 웹 검색 트리거에 필수)
#  - max_tokens 여유 확보 (thinking 채널 대비)
#
# 사전조건: run-webui.sh 로 Open WebUI가 떠 있고, 관리자 토큰이 필요하다.
#   OWUI_TOKEN=<관리자 API 토큰> ./seed-model.sh
set -euo pipefail

BASE="${OWUI_BASE:-http://127.0.0.1:3000}"
TOKEN="${OWUI_TOKEN:?관리자 API 토큰을 OWUI_TOKEN 환경변수로 전달하세요 (설정 > 계정 > API Key)}"
BASE_MODEL="${BASE_MODEL:-$HOME/Desktop/WebSearch/models/gemma-4-26b-a4b-it-4bit}"
MAX_TOKENS="${MAX_TOKENS:-2000}"

curl -fsS "$BASE/api/v1/models/create" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"mlx-community/gemma-4-26b-a4b-it-4bit\",
    \"base_model_id\": \"$BASE_MODEL\",
    \"name\": \"mlx-community/gemma-4-26b-a4b-it-4bit\",
    \"meta\": {\"description\": \"Gemma-4 (MLX) 로컬 · Legacy 웹 검색 기본\", \"capabilities\": {\"web_search\": true}},
    \"params\": {\"function_calling\": \"legacy\", \"max_tokens\": $MAX_TOKENS, \"temperature\": 0.6},
    \"is_active\": true
  }" | python3 -m json.tool
echo "완료: mlx-community/gemma-4-26b-a4b-it-4bit 등록됨 (function_calling=legacy)"
