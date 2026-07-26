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

source "$HERE/.venv/bin/activate"

echo "[model-server] model=$MODEL_PATH host=$MLX_HOST port=$MLX_PORT"
exec python -m mlx_lm server \
  --model "$MODEL_PATH" \
  --host "$MLX_HOST" \
  --port "$MLX_PORT" \
  --log-level INFO
