#!/bin/bash
# SearXNG 메타서치 서버 (Open WebUI 웹 검색 백엔드)
# 반드시 127.0.0.1 에만 바인딩한다. LAN/tailnet/공인 인터넷에 직접 노출하지 않는다.
#
# ddgs(DuckDuckGo) 를 대체한다. ddgs 는 다른 검색엔진을 비공식 스크래핑하는
# 라이브러리라 제공자 쪽 변화에 그대로 깨진다. SearXNG 는 자체 호스팅
# 메타서치라 API 키가 필요 없고 질의가 외부 대행 서비스로 나가지 않는다.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SEARXNG_PORT="${SEARXNG_PORT:-8888}"
SEARXNG_BIND_ADDRESS="${SEARXNG_BIND_ADDRESS:-127.0.0.1}"

# Flask 세션 서명용 시크릿. 없으면 최초 실행 시 생성해 .env 에 저장한다.
# (.env 는 git 미추적)
if [ -f "$HERE/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$HERE/.env"
  set +a
fi
if [ -z "${SEARXNG_SECRET:-}" ]; then
  SEARXNG_SECRET="$(openssl rand -hex 32)"
  printf 'SEARXNG_SECRET=%s\n' "$SEARXNG_SECRET" >> "$HERE/.env"
  echo "[searxng] SEARXNG_SECRET 생성해 .env 에 저장했습니다"
fi

export SEARXNG_SECRET
export SEARXNG_PORT
export SEARXNG_BIND_ADDRESS
export SEARXNG_SETTINGS_PATH="${SEARXNG_SETTINGS_PATH:-$HERE/settings.yml}"

source "$HERE/.venv/bin/activate"

echo "[searxng] host=$SEARXNG_BIND_ADDRESS port=$SEARXNG_PORT settings=$SEARXNG_SETTINGS_PATH"
exec searxng-run
