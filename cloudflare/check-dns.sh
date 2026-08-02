#!/bin/bash
# DNS 상태 점검 — 가비아 NS 위임과 터널 CNAME 이 제대로 걸렸는지 확인한다.
#
#   ./cloudflare/check-dns.sh
#
# 세 단계를 순서대로 본다.
#   1) 도메인의 권한 네임서버가 Cloudflare 인가        (가비아에서 바꾸는 부분)
#   2) 호스트명이 <TUNNEL_ID>.cfargotunnel.com 을 가리키는가  (cloudflared 가 만든다)
#   3) 실제 HTTPS 응답이 Access 로그인으로 리디렉션되는가
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$HERE/cloudflare.env" ] && { set -a; . "$HERE/cloudflare.env"; set +a; }

CF_DOMAIN="${CF_DOMAIN:-}"
CF_HOSTNAME="${CF_HOSTNAME:-}"
CF_TUNNEL_NAME="${CF_TUNNEL_NAME:-gemma}"

if [ -z "$CF_DOMAIN" ] || [ -z "$CF_HOSTNAME" ]; then
  echo "cloudflare/cloudflare.env 가 없거나 CF_DOMAIN/CF_HOSTNAME 이 비었다."
  echo "  cp cloudflare/cloudflare.env.example cloudflare/cloudflare.env"
  exit 1
fi

# 캐시된 리졸버 대신 권한 있는 답을 보기 위해 공개 리졸버를 쓴다.
RESOLVER="${DNS_RESOLVER:-1.1.1.1}"
FAIL=0

hr() { printf '\n=== %s ===\n' "$1"; }
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=1; }
warn() { printf '  \033[33mWARN\033[0m %s\n' "$1"; }

# ── 1. 네임서버 위임 ────────────────────────────────────────────────────
hr "1. 네임서버 위임 ($CF_DOMAIN)"

# 레지스트리(부모 존)에 등록된 위임 NS. 자식 존이 비어 REFUSED/SERVFAIL 이어도 보인다.
# 갓 구매해 존 설정을 안 한 도메인이 정확히 이 상태다.
ns_from_parent() {
  dig +trace +nodnssec +time=3 +tries=1 NS "$1" 2>/dev/null \
    | awk -v d="$1." '$1==d && $4=="NS" {print $5}' | sed 's/\.$//' | sort -u
}

NS="$(dig +short NS "$CF_DOMAIN" @"$RESOLVER" 2>/dev/null | sed 's/\.$//' | sort -u)"
NS_SRC="리졸버"
if [ -z "$NS" ]; then
  NS="$(ns_from_parent "$CF_DOMAIN")"
  NS_SRC="레지스트리(위임)"
fi

if [ -z "$NS" ]; then
  bad "위임 NS 를 찾을 수 없다 — 도메인 등록이 아직 반영되지 않았을 수 있다"
  echo "       가비아 > My가비아 > 도메인 에서 등록 상태를 먼저 확인한다."
  DELEGATED=no
elif echo "$NS" | grep -qi 'ns\.cloudflare\.com'; then
  ok "Cloudflare 네임서버로 위임됨 [$NS_SRC]"
  echo "$NS" | sed 's/^/       /'
  DELEGATED=yes
else
  bad "아직 Cloudflare 가 아닌 네임서버다 [$NS_SRC]"
  echo "$NS" | sed 's/^/       /'
  DELEGATED=no
  # 위임은 살아 있는데 리졸버가 답을 못 얻는 경우 = 존 데이터 없음.
  if [ "$NS_SRC" != "리졸버" ]; then
    warn "현재 이 네임서버들이 $CF_DOMAIN 존에 응답하지 않는다(SERVFAIL/REFUSED)."
    warn "구매만 하고 DNS 존을 만들지 않은 상태다. Cloudflare 로 옮기면 그대로 해결된다."
  fi
fi

if [ "$DELEGATED" != yes ]; then
  cat <<EOF

  ── 가비아에서 해야 할 일 ────────────────────────────────────────────
  a) Cloudflare 대시보드 > Add a site > "$CF_DOMAIN" 입력 > Free 플랜 선택
     → 기존 레코드 스캔 결과가 0건이어도 정상이다(신규 도메인이라 존이 비어 있다).
     → 배정된 네임서버 2개가 표시된다 (예: adam.ns.cloudflare.com / kate.ns.cloudflare.com)
       ※ 이 2개는 계정마다 다르다. 예시를 그대로 쓰지 말고 대시보드 값을 쓴다.

  b) 가비아 > My가비아 > 도메인 > "$CF_DOMAIN" 관리 > 네임서버 설정
     → 1차/2차 네임서버를 (a)에서 받은 값으로 교체하고 저장
     → 가비아 기본 네임서버(ns.gabia.co.kr 등)는 모두 지운다

  c) 저장 후 이 스크립트를 다시 실행한다.
     반영은 보통 10분~수 시간, .asia 는 최대 48시간까지 볼 수 있다.
     Cloudflare 대시보드의 zone 상태가 "Active" 가 되면 완료다.
EOF
fi

# ── 2. 터널 CNAME ──────────────────────────────────────────────────────
hr "2. 터널 CNAME ($CF_HOSTNAME)"
CNAME="$(dig +short CNAME "$CF_HOSTNAME" @"$RESOLVER" 2>/dev/null | sed 's/\.$//')"
ADDR="$(dig +short A "$CF_HOSTNAME" @"$RESOLVER" 2>/dev/null | head -3)"

# 로컬에 터널이 있으면 기대 UUID 를 뽑아 대조한다.
EXPECT_ID=""
if command -v cloudflared >/dev/null 2>&1; then
  EXPECT_ID="$(cloudflared tunnel list 2>/dev/null \
    | awk -v n="$CF_TUNNEL_NAME" '$2==n {print $1}' | head -1)"
fi

if [ -z "$CNAME" ] && [ -z "$ADDR" ]; then
  bad "$CF_HOSTNAME 이 해석되지 않는다"
  echo "       위임 완료 후 아래로 DNS 레코드를 만든다:"
  echo "         cloudflared tunnel route dns $CF_TUNNEL_NAME $CF_HOSTNAME"
  echo "       (setup-tunnel.sh 가 이 단계를 자동으로 수행한다)"
elif echo "$CNAME" | grep -q 'cfargotunnel\.com'; then
  ok "터널을 가리킨다: $CNAME"
  if [ -n "$EXPECT_ID" ]; then
    if echo "$CNAME" | grep -q "^$EXPECT_ID\."; then
      ok "터널 ID 일치 ($CF_TUNNEL_NAME = $EXPECT_ID)"
    else
      bad "터널 ID 불일치 — 로컬은 $EXPECT_ID, DNS 는 $CNAME"
      echo "       예전 터널의 레코드가 남아 있다. Cloudflare DNS 에서 지우고 다시 route 한다."
    fi
  fi
elif [ -n "$CNAME" ]; then
  bad "cfargotunnel 이 아닌 곳을 가리킨다: $CNAME"
else
  # Cloudflare 프록시가 켜져 있으면 A 로 Cloudflare 엣지 IP 가 보인다(정상).
  ok "A 레코드 응답 (Cloudflare 프록시 경유로 보임)"
  echo "$ADDR" | sed 's/^/       /'
fi

# ── 3. 엣지 응답과 Access 게이트 ────────────────────────────────────────
hr "3. HTTPS 응답 / Access 게이트"
if [ -z "$CNAME" ] && [ -z "$ADDR" ]; then
  warn "이름이 해석되지 않아 건너뛴다"
else
  # -o /dev/null 로 본문은 버리고 상태·리디렉션 대상만 본다. 인증은 하지 않는다.
  RESP="$(curl -s -o /dev/null -m 15 \
            -w '%{http_code} %{redirect_url}' \
            "https://$CF_HOSTNAME/" 2>/dev/null)"
  CODE="${RESP%% *}"
  LOC="${RESP#* }"

  case "$CODE" in
    302|303|307)
      if echo "$LOC" | grep -qE 'cloudflareaccess\.com|/cdn-cgi/access'; then
        ok "Access 로그인으로 리디렉션됨 ($CODE) — 게이트 정상"
      else
        bad "인증과 무관한 곳으로 리디렉션됨: $LOC"
      fi
      ;;
    200)
      bad "인증 없이 200 이 돌아온다 — Access 정책이 적용되지 않았다"
      echo "       Zero Trust > Access > Applications 에서 $CF_HOSTNAME 정책을 확인한다."
      echo "       이 상태로 두면 누구나 WebUI 에 닿는다."
      ;;
    530|1033)
      bad "$CODE — DNS 는 있는데 터널이 붙어 있지 않다 (cloudflared 미실행)"
      ;;
    502|503|504)
      bad "$CODE — 터널은 붙었으나 origin(127.0.0.1:3000)이 응답하지 않는다"
      ;;
    000)
      bad "연결 실패 (타임아웃/네트워크). 전파 중일 수 있다"
      ;;
    *)
      warn "예상 밖 상태코드: $CODE ${LOC:+-> $LOC}"
      ;;
  esac
fi

hr "결과"
if [ "$FAIL" -eq 0 ]; then
  echo "  모든 점검 통과."
else
  echo "  실패 항목이 있다. 위 안내를 따른다."
fi
exit "$FAIL"
