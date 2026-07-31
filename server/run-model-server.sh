#!/bin/bash
# Qwen3.6 MLX 모델 서버 (OpenAI 호환 API)
# 반드시 127.0.0.1 에만 바인딩한다. LAN/tailnet/공인 인터넷에 직접 노출하지 않는다.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

# --- 설정 (환경 변수로 덮어쓸 수 있음) ---
MODEL_PATH="${MODEL_PATH:-$REPO/models/Qwen3.6-35B-A3B-4bit}"
MLX_HOST="${MLX_HOST:-127.0.0.1}"
MLX_PORT="${MLX_PORT:-8080}"

# Qwen3.6 권장 샘플링 (모델 저장소의 generation_config.json 값과 동일).
# top-k 는 Open WebUI가 OpenAI 백엔드로 전달하지 않으므로 여기서 박아야 적용된다.
MLX_TEMP="${MLX_TEMP:-1.0}"
MLX_TOP_P="${MLX_TOP_P:-0.95}"
MLX_TOP_K="${MLX_TOP_K:-20}"

# Qwen3.6 thinking 채널 on/off (chat_template 의 enable_thinking 플래그).
# 추론과 최종 답변이 같은 출력 예산을 나눠 쓰는데, 웹 검색 요약 용도에서는
# 추론이 답변의 20배까지 길어져 응답이 40초대로 늘어난다. 기본은 끈다.
# 추론이 필요한 작업은 MLX_THINKING=on 으로 띄우거나, 요청 본문에
# chat_template_kwargs 를 넣어 요청 단위로 덮어쓴다.
# top-k 와 마찬가지로 Open WebUI가 전달하지 않으므로 서버에 박아야 적용된다.
MLX_THINKING="${MLX_THINKING:-off}"
if [ "$MLX_THINKING" = "on" ]; then
  CHAT_TEMPLATE_ARGS='{"enable_thinking":true}'
else
  CHAT_TEMPLATE_ARGS='{"enable_thinking":false}'
fi

source "$HERE/.venv/bin/activate"

echo "[model-server] model=$MODEL_PATH host=$MLX_HOST port=$MLX_PORT temp=$MLX_TEMP top_p=$MLX_TOP_P top_k=$MLX_TOP_K thinking=$MLX_THINKING"
exec python -m mlx_lm server \
  --model "$MODEL_PATH" \
  --host "$MLX_HOST" \
  --port "$MLX_PORT" \
  --temp "$MLX_TEMP" \
  --top-p "$MLX_TOP_P" \
  --top-k "$MLX_TOP_K" \
  --chat-template-args "$CHAT_TEMPLATE_ARGS" \
  --log-level INFO
