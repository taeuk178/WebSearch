#!/bin/bash
# 로컬 LLM 스택 기동: model-server → searxng → webui → cloudflared 순으로 올린다.
# LaunchAgent 를 load 하므로 이후 비정상 종료 시 KeepAlive 가 알아서 되살린다.
#
# 사용:
#   ./scripts/server_on.sh            # 기동 + 헬스체크 대기
#   ./scripts/server_on.sh --no-wait  # 기동만 하고 즉시 반환
#
# 정지: ./scripts/server_off.sh
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LA_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/gemma"

WAIT=1
case "${1:-}" in
  --no-wait) WAIT=0 ;;
  "") ;;
  *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
esac

# 의존 순서대로 올린다. webui 는 model-server/searxng 를 물고,
# cloudflared 는 webui 가 떠 있어야 502 를 안 뿌린다.
LABELS=(dev.gemma.model-server dev.gemma.searxng dev.gemma.webui)
if [ -f "$REPO/cloudflare/config.yml" ]; then
  LABELS+=(dev.gemma.cloudflared)
fi

# plist 가 하나라도 없으면 설치부터. 생성과 로드를 install 쪽이 함께 처리한다.
MISSING=0
for L in "${LABELS[@]}"; do
  [ -f "$LA_DIR/$L.plist" ] || MISSING=1
done
if [ "$MISSING" -eq 1 ]; then
  echo "LaunchAgent plist 가 없어 install-launchagents.sh 로 등록한다."
  "$REPO/scripts/install-launchagents.sh"
else
  for L in "${LABELS[@]}"; do
    if launchctl list "$L" >/dev/null 2>&1; then
      echo "이미 실행 중: $L"
      continue
    fi
    if launchctl load "$LA_DIR/$L.plist" 2>/dev/null; then
      echo "기동: $L"
    else
      echo "기동 실패: $L (로그: $LOG_DIR/*.err.log)" >&2
    fi
  done
fi

if [ "$WAIT" -eq 0 ]; then
  echo
  echo "상태 확인: ./scripts/status.sh"
  exit 0
fi

# 35B 모델은 첫 로드에 수십 초가 걸린다. 폴링해서 실제로 응답할 때까지 기다린다.
wait_health() {
  local name="$1" url="$2" timeout="$3" start=$SECONDS elapsed
  printf "  %-10s " "$name"
  while :; do
    if curl -sf -m 3 "$url" >/dev/null 2>&1; then
      echo " OK ($((SECONDS - start))초)"
      return 0
    fi
    elapsed=$((SECONDS - start))
    if [ "$elapsed" -ge "$timeout" ]; then
      echo " 시간초과 (${timeout}초)"
      return 1
    fi
    printf "."
    sleep 3
  done
}

echo
echo "=== 헬스체크 ==="
RC=0
wait_health "MLX:8080"  "http://127.0.0.1:8080/v1/models"                    300 || RC=1
wait_health "SearXNG"   "http://127.0.0.1:8888/search?q=test&format=json"     90 || RC=1
wait_health "WebUI:3000" "http://127.0.0.1:3000/health"                      180 || RC=1
if [ -f "$REPO/cloudflare/config.yml" ]; then
  wait_health "Tunnel"  "http://127.0.0.1:20241/ready"                        90 || RC=1
fi

echo
if [ "$RC" -eq 0 ]; then
  echo "전체 정상. 접속: http://127.0.0.1:3000"
  if [ -f "$REPO/cloudflare/config.yml" ]; then
    CF_HOST="$(awk '/^[[:space:]]*- hostname:/ {print $3; exit}' "$REPO/cloudflare/config.yml")"
    [ -n "${CF_HOST:-}" ] && echo "원격    : https://$CF_HOST"
  fi
else
  echo "일부 서비스가 응답하지 않는다. 로그를 확인한다:"
  echo "  tail -20 $LOG_DIR/*.err.log"
  echo "  ./scripts/status.sh"
fi
exit "$RC"
