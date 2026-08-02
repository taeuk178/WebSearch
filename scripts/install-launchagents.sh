#!/bin/bash
# Mac mini에서 실행: 모델 서버 + SearXNG + Open WebUI 를 사용자 LaunchAgent로 등록한다.
# 로그인 시 자동 실행되고, 비정상 종료 시 재시작된다(KeepAlive).
#
# 사용:
#   ./scripts/install-launchagents.sh          # 생성 + 로드
#   ./scripts/install-launchagents.sh --reload  # 언로드 후 재로드
#   ./scripts/install-launchagents.sh --uninstall
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LA_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/gemma"
# searxng 는 웹 검색 백엔드. 없으면 검색만 실패하고 대화는 정상 동작한다.
LABELS=(dev.gemma.model-server dev.gemma.searxng dev.gemma.webui)

# cloudflared(원격 접속 터널)는 설정이 끝난 뒤에만 등록한다.
# config.yml 없이 로드하면 기동 실패 → KeepAlive 재시작 루프만 돈다.
if [ -f "$REPO/cloudflare/config.yml" ]; then
  LABELS+=(dev.gemma.cloudflared)
else
  echo "안내: cloudflare/config.yml 이 없어 터널은 등록하지 않는다."
  echo "      원격 접속이 필요하면 먼저 ./cloudflare/setup-tunnel.sh 를 실행한다."
fi

# 제거는 등록 여부와 무관하게 전부 훑는다(설정을 지운 뒤에도 정리되도록).
ALL_LABELS=(dev.gemma.model-server dev.gemma.searxng dev.gemma.webui dev.gemma.cloudflared)

uninstall() {
  for L in "${ALL_LABELS[@]}"; do
    launchctl unload "$LA_DIR/$L.plist" 2>/dev/null || true
    rm -f "$LA_DIR/$L.plist"
    echo "제거: $L"
  done
}

case "${1:-}" in
  --uninstall) uninstall; exit 0 ;;
  --reload)    for L in "${ALL_LABELS[@]}"; do launchctl unload "$LA_DIR/$L.plist" 2>/dev/null || true; done ;;
esac

mkdir -p "$LA_DIR" "$LOG_DIR"

for L in "${LABELS[@]}"; do
  src="$REPO/launchd/$L.plist.template"
  dst="$LA_DIR/$L.plist"
  sed -e "s#__REPO__#$REPO#g" -e "s#__LOGDIR__#$LOG_DIR#g" "$src" > "$dst"
  launchctl unload "$dst" 2>/dev/null || true
  launchctl load "$dst"
  echo "로드: $L -> $dst"
done

echo
echo "상태 확인:  launchctl list | grep gemma"
echo "로그:       $LOG_DIR/*.log"
echo "해제:       $0 --uninstall"
