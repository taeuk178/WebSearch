#!/bin/bash
# Cloudflare Tunnel 구축 — Mac mini 에서 실행한다.
#
#   ./cloudflare/setup-tunnel.sh            # 전체 절차 (여러 번 실행해도 안전)
#   ./cloudflare/setup-tunnel.sh --check     # 변경 없이 현재 상태만 점검
#   ./cloudflare/setup-tunnel.sh --skip-dns  # DNS 라우팅만 건너뛰기
#
# 이 스크립트는 **인증 설정을 하지 않는다.** Access 애플리케이션과 정책은
# Cloudflare Zero Trust 대시보드에서 사람이 만들어야 하며, 그것이 끝나기 전에는
# DNS 라우팅을 하지 않는 것이 안전하다(라우팅되는 순간 공개 접점이 생긴다).
# 절차는 docs/remote-access.md 를 따른다.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
CONFIG="$HERE/config.yml"
TEMPLATE="$HERE/config.yml.template"
CFDIR="$HOME/.cloudflared"

CHECK_ONLY=no
SKIP_DNS=no
for a in "$@"; do
  case "$a" in
    --check)    CHECK_ONLY=yes ;;
    --skip-dns) SKIP_DNS=yes ;;
    *) echo "알 수 없는 옵션: $a" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m── %s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$1" >&2; exit 1; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }

# ── 0. 설정 로드 ────────────────────────────────────────────────────────
step "0. 설정"
if [ ! -f "$HERE/cloudflare.env" ]; then
  die "cloudflare/cloudflare.env 가 없다.  cp cloudflare/cloudflare.env.example cloudflare/cloudflare.env"
fi
set -a; . "$HERE/cloudflare.env"; set +a

: "${CF_DOMAIN:?cloudflare.env 에 CF_DOMAIN 이 필요하다}"
: "${CF_HOSTNAME:?cloudflare.env 에 CF_HOSTNAME 이 필요하다}"
CF_TUNNEL_NAME="${CF_TUNNEL_NAME:-gemma}"
CF_SERVICE_URL="${CF_SERVICE_URL:-http://127.0.0.1:3000}"
CF_PROTOCOL="${CF_PROTOCOL:-auto}"

case "$CF_HOSTNAME" in
  *".$CF_DOMAIN"|"$CF_DOMAIN") ;;
  *) die "CF_HOSTNAME($CF_HOSTNAME) 이 CF_DOMAIN($CF_DOMAIN) 에 속하지 않는다" ;;
esac
ok "도메인=$CF_DOMAIN  호스트=$CF_HOSTNAME  터널=$CF_TUNNEL_NAME  대상=$CF_SERVICE_URL"

# 노출 대상은 3000 하나여야 한다. 여기서 막지 않으면 config 로 흘러간다.
case "$CF_SERVICE_URL" in
  *:8080*|*:8888*) die "CF_SERVICE_URL 이 8080/8888 을 가리킨다. 모델 API·검색엔진은 절대 노출하지 않는다" ;;
esac

# ── 1. 선행 조건 (ROADMAP 7-4 A) ────────────────────────────────────────
step "1. 선행 조건 점검"
PRE_FAIL=0

ENVF="$REPO/webui/.env"
if [ -f "$ENVF" ]; then
  if grep -qiE '^ENABLE_SIGNUP[[:space:]]*=[[:space:]]*True' "$ENVF"; then
    warn "webui/.env: ENABLE_SIGNUP=True — 공개되면 누구나 계정을 만든다"; PRE_FAIL=1
  else ok "webui/.env: 가입 차단됨"; fi

  if grep -qiE '^DEFAULT_USER_ROLE[[:space:]]*=[[:space:]]*admin' "$ENVF"; then
    warn "webui/.env: DEFAULT_USER_ROLE=admin — 새 계정이 곧바로 관리자가 된다"; PRE_FAIL=1
  else ok "webui/.env: 기본 역할 안전"; fi
else
  warn "webui/.env 가 없다"; PRE_FAIL=1
fi

# 세 서비스가 루프백에만 묶여 있어야 터널 외 경로가 생기지 않는다.
# lsof 는 결과가 없으면 1 을 낸다. pipefail + set -e 조합에서 스크립트가 죽으므로 || true.
for p in 3000 8080 8888; do
  BIND="$(lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $9}' | sort -u || true)"
  if [ -z "$BIND" ]; then
    warn "포트 $p 리스닝 없음 (서비스 미기동)"
  elif echo "$BIND" | grep -qv '^127\.0\.0\.1:'; then
    warn "포트 $p 가 루프백 외에도 바인딩됨: $(echo "$BIND" | tr '\n' ' ')"; PRE_FAIL=1
  else
    ok "포트 $p 루프백 전용"
  fi
done

if [ "$PRE_FAIL" -ne 0 ]; then
  echo
  warn "선행 조건이 충족되지 않았다. 지금 DNS 라우팅까지 하면 지금보다 덜 안전해진다."
  warn "docs/remote-access.md 2장을 먼저 처리할 것. (터널 생성까지는 계속 진행한다)"
  SKIP_DNS=yes
fi

# ── 2. cloudflared 설치 ────────────────────────────────────────────────
step "2. cloudflared"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if command -v cloudflared >/dev/null 2>&1; then
  ok "설치됨: $(cloudflared --version 2>&1 | head -1)"
elif [ "$CHECK_ONLY" = yes ]; then
  die "cloudflared 미설치"
else
  command -v brew >/dev/null 2>&1 || die "Homebrew 가 없다. cloudflared 를 수동 설치할 것"
  echo "  brew install cloudflared ..."
  brew install cloudflared
  ok "설치 완료: $(cloudflared --version 2>&1 | head -1)"
fi

# ── 3. 계정 인증서 ─────────────────────────────────────────────────────
step "3. 계정 인증 (cert.pem)"
if [ -f "$CFDIR/cert.pem" ]; then
  ok "$CFDIR/cert.pem 존재"
elif [ "$CHECK_ONLY" = yes ]; then
  die "cert.pem 없음 — cloudflared tunnel login 필요"
else
  cat <<EOF
  브라우저가 열린다. Cloudflare 로그인 후 "$CF_DOMAIN" zone 을 선택하면
  $CFDIR/cert.pem 이 발급된다.

  ⚠ 목록에 "$CF_DOMAIN" 이 없다면 아직 Cloudflare 에 사이트가 추가되지 않은 것이다.
     대시보드에서 Add a site 로 등록하고, 가비아에서 네임서버를 위임한 뒤
     zone 상태가 Active 가 되어야 한다. 자세한 절차:  ./cloudflare/check-dns.sh
EOF
  read -r -p "  계속하려면 Enter (중단하려면 Ctrl-C): " _
  cloudflared tunnel login
  [ -f "$CFDIR/cert.pem" ] || die "cert.pem 이 생성되지 않았다"
  ok "발급 완료"
fi

# ── 4. 터널 생성 ───────────────────────────────────────────────────────
step "4. 터널 '$CF_TUNNEL_NAME'"
# --name 으로 서버에서 걸러 받고 id 만 뽑는다(삭제된 터널은 목록에 없다).
# 외부 파서 의존을 피하려고 grep 으로 처리한다.
tunnel_id() {
  cloudflared tunnel list --name "$CF_TUNNEL_NAME" --output json 2>/dev/null \
    | grep -o '"id"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -1 | sed 's/.*"\([^"]*\)"$/\1/' || true
}

TUNNEL_ID="$(tunnel_id)"
if [ -n "$TUNNEL_ID" ]; then
  ok "이미 존재: $TUNNEL_ID"
elif [ "$CHECK_ONLY" = yes ]; then
  die "터널 미생성"
else
  cloudflared tunnel create "$CF_TUNNEL_NAME"
  TUNNEL_ID="$(tunnel_id)"
  [ -n "$TUNNEL_ID" ] || die "터널 ID 를 확인할 수 없다"
  ok "생성됨: $TUNNEL_ID"
fi

CRED="$CFDIR/$TUNNEL_ID.json"
[ -f "$CRED" ] || die "자격증명 파일이 없다: $CRED"
ok "자격증명: $CRED"

# ── 5. config.yml 생성 ─────────────────────────────────────────────────
step "5. config.yml"
if [ "$CHECK_ONLY" = yes ]; then
  [ -f "$CONFIG" ] && ok "존재: $CONFIG" || die "config.yml 없음"
else
  sed -e "s#__TUNNEL_ID__#$TUNNEL_ID#g" \
      -e "s#__CREDENTIALS_FILE__#$CRED#g" \
      -e "s#__HOSTNAME__#$CF_HOSTNAME#g" \
      -e "s#__SERVICE_URL__#$CF_SERVICE_URL#g" \
      -e "s#__PROTOCOL__#$CF_PROTOCOL#g" \
      "$TEMPLATE" > "$CONFIG"
  chmod 600 "$CONFIG"
  ok "생성: $CONFIG"
fi

# ── 6. ingress 검증 ────────────────────────────────────────────────────
step "6. ingress 검증"
cloudflared --config "$CONFIG" tunnel ingress validate \
  || die "ingress 규칙이 유효하지 않다"
ok "규칙 유효"

MATCH="$(cloudflared --config "$CONFIG" tunnel ingress rule "https://$CF_HOSTNAME/" 2>&1 || true)"
if echo "$MATCH" | grep -q "$CF_SERVICE_URL"; then
  ok "$CF_HOSTNAME → $CF_SERVICE_URL"
else
  warn "매칭 결과 확인 필요: $MATCH"
fi

# catch-all 이 없으면 의도치 않은 호스트명이 WebUI 로 흘러든다. 실패면 중단한다.
UNMATCHED="$(cloudflared --config "$CONFIG" tunnel ingress rule "https://unmatched.$CF_DOMAIN/" 2>&1 || true)"
if echo "$UNMATCHED" | grep -q 'http_status:404'; then
  ok "그 외 호스트 → 404 (catch-all 정상)"
else
  die "catch-all 규칙이 동작하지 않는다: $UNMATCHED"
fi

# ── 7. DNS 라우팅 ──────────────────────────────────────────────────────
step "7. DNS 라우팅"
if [ "$CHECK_ONLY" = yes ] || [ "$SKIP_DNS" = yes ]; then
  warn "건너뜀. 준비되면:  cloudflared tunnel route dns $CF_TUNNEL_NAME $CF_HOSTNAME"
else
  cat <<EOF
  이 단계는 $CF_HOSTNAME 을 인터넷에 **공개 접점으로 만든다.**

  진행 전 확인:
    - Zero Trust > Access > Applications 에 $CF_HOSTNAME 애플리케이션이 있는가
    - 정책이 "지정 이메일만 허용" 인가 ("인증된 아무나" 는 금지)
    - Open WebUI 가입이 잠겨 있는가 (ENABLE_SIGNUP=False)

  아직이라면 지금 Ctrl-C 로 중단하고, Access 를 먼저 만든 뒤 다시 실행한다.
EOF
  read -r -p "  Access 정책이 준비됐으면 'yes' 입력: " ANS
  if [ "$ANS" = yes ]; then
    cloudflared tunnel route dns "$CF_TUNNEL_NAME" "$CF_HOSTNAME" \
      && ok "DNS 레코드 생성: $CF_HOSTNAME → $TUNNEL_ID.cfargotunnel.com" \
      || warn "라우팅 실패 — zone 이 Active 인지 확인:  ./cloudflare/check-dns.sh"
  else
    warn "건너뜀. 준비되면:  cloudflared tunnel route dns $CF_TUNNEL_NAME $CF_HOSTNAME"
  fi
fi

# ── 마무리 ─────────────────────────────────────────────────────────────
step "다음 단계"
cat <<EOF
  1) 수동 기동으로 확인:   ./cloudflare/run-cloudflared.sh
  2) DNS/Access 점검:      ./cloudflare/check-dns.sh
  3) 상시 운영 등록:       ./scripts/install-launchagents.sh --reload
  4) 전체 상태:            ./scripts/status.sh
EOF
