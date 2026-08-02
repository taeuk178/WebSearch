#!/bin/bash
# Mac mini 상태 점검: 포트/바인딩, 헬스, LaunchAgent, 메모리, Tailscale, 최근 로그.
set -uo pipefail
LOG_DIR="$HOME/Library/Logs/gemma"

hr() { printf '\n=== %s ===\n' "$1"; }

hr "포트 바인딩 (127.0.0.1 에만 있어야 함)"
lsof -nP -iTCP:8080 -sTCP:LISTEN 2>/dev/null || echo "  8080(MLX) 리스닝 없음"
lsof -nP -iTCP:8888 -sTCP:LISTEN 2>/dev/null || echo "  8888(SearXNG) 리스닝 없음"
lsof -nP -iTCP:3000 -sTCP:LISTEN 2>/dev/null || echo "  3000(WebUI) 리스닝 없음"

hr "헬스체크"
printf "  MLX   /v1/models : "; curl -sf http://127.0.0.1:8080/v1/models >/dev/null && echo OK || echo FAIL
printf "  SearXNG /search  : "; curl -sf "http://127.0.0.1:8888/search?q=test&format=json" >/dev/null && echo OK || echo FAIL
printf "  WebUI /health    : "; curl -sf http://127.0.0.1:3000/health   >/dev/null && echo OK || echo FAIL

hr "LaunchAgent"
launchctl list 2>/dev/null | grep -i gemma || echo "  gemma LaunchAgent 미등록 (수동 실행 중일 수 있음)"

hr "메모리"
echo "  $(memory_pressure 2>/dev/null | grep -i 'System-wide memory free percentage' || true)"
ps -axo rss,comm 2>/dev/null | awk '/mlx_lm|python.*server|open_webui|open-webui|searxng/ {sum+=$1} END {printf "  관련 프로세스 RSS 합계: %.1f GB\n", sum/1024/1024}'

hr "Tailscale"
command -v tailscale >/dev/null 2>&1 && tailscale status 2>/dev/null | head -5 || echo "  tailscale CLI 없음/미연결"

hr "Cloudflare Tunnel"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CF_CONF="$REPO_DIR/cloudflare/config.yml"
if [ ! -f "$CF_CONF" ]; then
  echo "  미구성 (cloudflare/setup-tunnel.sh 미실행)"
else
  CF_HOST="$(awk '/^[[:space:]]*- hostname:/ {print $3; exit}' "$CF_CONF")"
  echo "  호스트명    : ${CF_HOST:-?}"
  # ingress 에 3000 외의 포트가 섞이면 그 자체가 사고다. 매번 눈에 띄게 본다.
  if grep -Eq 'service:[[:space:]]*https?://(127\.0\.0\.1|localhost):(8080|8888)' "$CF_CONF"; then
    echo "  ⚠ 경고      : ingress 에 8080/8888 이 있다 — 모델 API 가 공개된다"
  else
    echo "  ingress     : 3000 만 노출 (정상)"
  fi
  printf "  프로세스    : "; pgrep -fl 'cloudflared.*tunnel run' >/dev/null 2>&1 && echo "실행 중" || echo "없음"
  # config.yml 의 metrics 주소. 터널이 엣지에 실제로 붙었는지 여기로 확인한다.
  printf "  엣지 연결   : "
  if CF_READY="$(curl -sf -m 3 http://127.0.0.1:20241/ready 2>/dev/null)"; then
    echo "$CF_READY"
  else
    echo "확인 불가 (metrics 127.0.0.1:20241 미응답)"
  fi
  if [ -n "${CF_HOST:-}" ]; then
    # curl 이 실패해도 -w 는 000 을 찍는다. 변수로 받아 한 줄만 낸다.
    CF_CODE="$(curl -s -o /dev/null -m 10 -w '%{http_code}' "https://$CF_HOST/" 2>/dev/null || true)"
    echo "  외부 응답   : ${CF_CODE:-000} (000=연결 실패)"
    echo "                302=Access 로그인 리디렉션이 정상, 200=인증 없이 열림"
  fi
fi

hr "최근 로그 (tail)"
for f in "$LOG_DIR"/model-server.err.log "$LOG_DIR"/searxng.err.log "$LOG_DIR"/webui.err.log "$LOG_DIR"/cloudflared.err.log; do
  [ -f "$f" ] && { echo "--- $f"; tail -3 "$f"; }
done
