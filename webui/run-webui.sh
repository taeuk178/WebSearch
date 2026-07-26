#!/bin/bash
# Open WebUI 실행 (127.0.0.1 에만 바인딩)
# LAN/tailnet/공인 인터넷에 직접 노출하지 않는다. 원격 접속은 SSH 터널로만.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WEBUI_HOST="${WEBUI_HOST:-127.0.0.1}"
WEBUI_PORT="${WEBUI_PORT:-3000}"

# 영구 데이터 경로 (계정/설정 보존). 검색·대화 내용은 여기에 영구 저장하지 않는다.
export DATA_DIR="${DATA_DIR:-$HERE/data}"
mkdir -p "$DATA_DIR"

# .env 로 설정 주입
if [ -f "$HERE/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$HERE/.env"
  set +a
fi

source "$HERE/.venv/bin/activate"

echo "[open-webui] host=$WEBUI_HOST port=$WEBUI_PORT data=$DATA_DIR"
exec open-webui serve --host "$WEBUI_HOST" --port "$WEBUI_PORT"
