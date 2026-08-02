#!/bin/bash
# cloudflared 터널 실행. LaunchAgent(dev.gemma.cloudflared)가 이걸 호출한다.
# 수동 실행도 가능: ./cloudflare/run-cloudflared.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$HERE/config.yml"

# launchd 환경은 PATH 가 최소라 brew 경로를 명시적으로 붙인다(Apple Silicon/Intel 둘 다).
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ ! -f "$CONFIG" ]; then
  echo "[cloudflared] $CONFIG 가 없다. 먼저 ./cloudflare/setup-tunnel.sh 를 실행한다." >&2
  exit 1
fi

# ── 안전장치 ────────────────────────────────────────────────────────────
# ingress 에 3000 외의 로컬 포트가 들어가면 인증 없는 모델 API(8080)나
# SearXNG(8888)가 공개된다. 사고 비용이 크므로 기동 자체를 막는다.
# cloudflared 유무와 무관하게 항상 걸리도록 바이너리 확인보다 먼저 둔다.
if grep -Eq 'service:[[:space:]]*https?://(127\.0\.0\.1|localhost):(8080|8888)' "$CONFIG"; then
  echo "[cloudflared] 중단: config.yml 의 ingress 에 8080/8888 이 있다." >&2
  echo "[cloudflared] 이대로 띄우면 인증 없는 모델 API 가 인터넷에 열린다." >&2
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "[cloudflared] 실행 파일을 찾을 수 없다. brew install cloudflared" >&2
  exit 1
fi

# 설정 문법과 catch-all 규칙을 매 기동마다 검증한다.
if ! cloudflared --config "$CONFIG" tunnel ingress validate; then
  echo "[cloudflared] ingress 검증 실패. 기동하지 않는다." >&2
  exit 1
fi

echo "[cloudflared] config=$CONFIG"
exec cloudflared --config "$CONFIG" --no-autoupdate tunnel run
