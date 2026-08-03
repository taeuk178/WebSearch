#!/bin/bash
# 로컬 LLM 스택 정지: cloudflared → webui → searxng → model-server 순으로 내린다.
# LaunchAgent 를 unload 하므로 KeepAlive 자동 재시작도 함께 멈춘다.
#
# plist 는 남겨둔다 → 재부팅/재로그인 시 다시 자동 실행된다.
# 자동 실행까지 끊으려면: ./scripts/install-launchagents.sh --uninstall
#
# 사용:
#   ./scripts/server_off.sh          # 전체 정지
#   ./scripts/server_off.sh --force  # 남은 수동 실행 프로세스까지 종료
#
# 기동: ./scripts/server_on.sh
set -uo pipefail

LA_DIR="$HOME/Library/LaunchAgents"

FORCE=0
case "${1:-}" in
  --force) FORCE=1 ;;
  "") ;;
  *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
esac

# 외부 노출을 먼저 끊는다. 터널만 살아 있으면 방문자에게 502 를 뿌린다.
# 등록 여부와 무관하게 전부 훑는다.
LABELS=(dev.gemma.cloudflared dev.gemma.webui dev.gemma.searxng dev.gemma.model-server)

for L in "${LABELS[@]}"; do
  if [ ! -f "$LA_DIR/$L.plist" ]; then
    echo "건너뜀: $L (plist 없음)"
    continue
  fi
  if ! launchctl list "$L" >/dev/null 2>&1; then
    echo "이미 정지: $L"
    continue
  fi
  launchctl unload "$LA_DIR/$L.plist" 2>/dev/null
  echo "정지: $L"
done

sleep 2

# LaunchAgent 밖에서 수동으로 띄운 프로세스는 unload 로 안 죽는다.
PATTERN='mlx_lm[ .]server|open-webui serve|searxng-run|cloudflared.*tunnel run'
LEFT="$(pgrep -f "$PATTERN" 2>/dev/null || true)"

if [ -n "$LEFT" ]; then
  echo
  if [ "$FORCE" -eq 1 ]; then
    echo "=== 잔여 프로세스 종료 ==="
    pgrep -fl "$PATTERN" 2>/dev/null
    pkill -f "$PATTERN" 2>/dev/null
    sleep 3
    # SIGTERM 을 무시하면 그때만 -9.
    if pgrep -f "$PATTERN" >/dev/null 2>&1; then
      pkill -9 -f "$PATTERN" 2>/dev/null
      sleep 1
    fi
  else
    echo "=== 경고: LaunchAgent 밖 프로세스가 남아 있다 (수동 실행분) ==="
    pgrep -fl "$PATTERN" 2>/dev/null
    echo "종료하려면: ./scripts/server_off.sh --force"
  fi
fi

echo
echo "=== 포트 확인 ==="
RC=0
for P in 8080 8888 3000; do
  if lsof -nP -iTCP:"$P" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "  $P: 아직 리스닝 중"
    RC=1
  else
    echo "  $P: 닫힘"
  fi
done

echo
if [ "$RC" -eq 0 ]; then
  echo "전체 정지 완료."
else
  echo "일부 포트가 열려 있다. ./scripts/status.sh 로 확인한다."
fi
echo "재부팅하면 다시 자동 실행된다. 완전히 끊으려면: ./scripts/install-launchagents.sh --uninstall"
exit "$RC"
