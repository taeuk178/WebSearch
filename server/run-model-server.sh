#!/bin/bash
# Gemma-4 MLX 모델 서버 (OpenAI 호환 API)
# 반드시 127.0.0.1 에만 바인딩한다. LAN/tailnet/공인 인터넷에 직접 노출하지 않는다.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

# --- 설정 (환경 변수로 덮어쓸 수 있음) ---
MODEL_PATH="${MODEL_PATH:-$REPO/models/gemma-4-26b-a4b-it-4bit}"
MLX_HOST="${MLX_HOST:-127.0.0.1}"
MLX_PORT="${MLX_PORT:-8080}"

# gemma-4 권장 샘플링을 서버 기본값으로 고정.
# 특히 top-k 는 Open WebUI가 OpenAI 백엔드로 전달하지 않으므로 여기서 박아야
# gemma-4 thinking 채널의 반복 루프를 막을 수 있다.
MLX_TEMP="${MLX_TEMP:-1.0}"
MLX_TOP_P="${MLX_TOP_P:-0.95}"
MLX_TOP_K="${MLX_TOP_K:-64}"

source "$HERE/.venv/bin/activate"

echo "[model-server] model=$MODEL_PATH host=$MLX_HOST port=$MLX_PORT temp=$MLX_TEMP top_p=$MLX_TOP_P top_k=$MLX_TOP_K"
exec python -m mlx_lm server \
  --model "$MODEL_PATH" \
  --host "$MLX_HOST" \
  --port "$MLX_PORT" \
  --temp "$MLX_TEMP" \
  --top-p "$MLX_TOP_P" \
  --top-k "$MLX_TOP_K" \
  --log-level INFO
