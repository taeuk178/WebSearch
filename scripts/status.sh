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

hr "최근 로그 (tail)"
for f in "$LOG_DIR"/model-server.err.log "$LOG_DIR"/searxng.err.log "$LOG_DIR"/webui.err.log; do
  [ -f "$f" ] && { echo "--- $f"; tail -3 "$f"; }
done
