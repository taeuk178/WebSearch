# 원격 접속 (Cloudflare Tunnel + Access)

사내 맥북과 개인 맥북에서 **같은 방법으로** 접속하기 위한 경로다.
방안 비교와 결정 근거는 `ROADMAP.md` 7-1, 감수한 트레이드오프는 7-2 에 있다.

이 문서는 절차만 다룬다.

- 도메인: `imprint.asia` (가비아 구매)
- 공개 호스트명: `ai.imprint.asia` — **인터넷에 노출되는 이름은 이것 하나뿐이다**
- 노출 대상: Open WebUI `127.0.0.1:3000` 만. 8080(MLX)·8888(SearXNG)은 절대 넣지 않는다

```
사내/개인 맥북 ──HTTPS 443──▶ Cloudflare 엣지 ──Access 인증──▶ 터널 ──▶ Mac mini 127.0.0.1:3000
                                     ▲
                          여기서 TLS 가 종료된다(7-2)
```

기존 Tailscale + SSH 터널(`docs/usage.md`)은 **그대로 둔다.** 개인 맥북에서는
계속 그 경로가 더 안전하고, Cloudflare 가 죽었을 때의 대체 경로가 된다.

---

## 0. 순서가 중요하다

DNS 라우팅을 하는 순간 `ai.imprint.asia` 는 공개 접점이 된다.
**Access 정책이 먼저 있어야 한다.** 순서를 지킨다.

```
1. 선행 조건 (가입 잠금 · SSH 하드닝 · 바인딩 확인)
2. Cloudflare 에 도메인 등록 + 가비아 네임서버 위임      ← DNS 작업
3. Access 애플리케이션·정책 생성                          ← 인증 먼저
4. 터널 생성 + config.yml                                 ← setup-tunnel.sh
5. DNS 라우팅 (여기서 공개된다)
6. 상시 운영 등록 (LaunchAgent)
```

---

## 1. 선행 조건

`ROADMAP.md` 7-4 A 항목이다. `setup-tunnel.sh` 가 자동으로 점검하고,
충족되지 않으면 DNS 라우팅 단계를 스스로 건너뛴다.

```bash
# 가입이 잠겨 있는지
grep -E 'ENABLE_SIGNUP|DEFAULT_USER_ROLE' webui/.env
# → ENABLE_SIGNUP=False / DEFAULT_USER_ROLE=pending 이어야 한다

# 세 서비스가 루프백에만 묶여 있는지
./scripts/status.sh
```

`.env` 를 고쳤으면 **Open WebUI 를 재시작**해야 반영된다
(`ENABLE_PERSISTENT_CONFIG=False` 이므로 `.env` 가 런타임 설정의 기준이다).

```bash
launchctl kickstart -k "gui/$(id -u)/dev.gemma.webui"
```

재시작 후 시크릿 창에서 `http://127.0.0.1:3000/auth` 를 열어 가입 폼이
사라졌는지 눈으로 확인한다. 그리고 불필요한 관리자 계정을 지운다 —
설정 > 관리자 패널 > 사용자.

SSH 하드닝은 `docs/security.md` 3-3 을 따른다.

---

## 2. DNS — Cloudflare 등록과 가비아 위임

가비아에서 산 도메인은 가비아 네임서버로 위임돼 있다. Cloudflare Tunnel 은
**해당 zone 이 Cloudflare 에 있어야** DNS 레코드를 만들 수 있으므로, 네임서버를
Cloudflare 로 옮긴다. 도메인 소유권은 그대로 가비아에 남는다 — 이전(transfer)이
아니라 위임(delegation)만 바꾸는 것이다.

### 2-1. 현재 상태 확인

```bash
cp cloudflare/cloudflare.env.example cloudflare/cloudflare.env   # 최초 1회
./cloudflare/check-dns.sh
```

`imprint.asia` 는 구매 직후라 가비아 네임서버로 위임돼 있으나 **존 데이터가 없어
조회가 SERVFAIL** 인 상태다. 정상이다. Cloudflare 로 옮기면 해결된다.

### 2-2. Cloudflare 에 사이트 추가

1. Cloudflare 대시보드 > **Add a site** > `imprint.asia` > **Free** 플랜
2. 기존 레코드 스캔 결과가 **0건이어도 정상**이다 (신규 도메인이라 존이 비어 있다).
   MX·`www`·루트 A 레코드를 추가하라는 안내가 뜨지만 전부 필요 없다.
   `ai` 레코드도 지금 만들지 않는다 — 터널 UUID 가 있어야 하므로
   `cloudflared tunnel route dns` 가 나중에 만든다
3. **Continue to activation** → 배정된 네임서버 2개 확인

**이 도메인에 배정된 값 (2026-08-02)**

| | 호스트명 |
|---|---|
| 1차 | `aldo.ns.cloudflare.com` |
| 2차 | `maya.ns.cloudflare.com` |

> 이 값은 zone 마다 다르다. zone 을 지웠다 다시 만들면 재배정될 수 있으므로,
> 그때는 대시보드 값을 다시 확인한다.

### 2-3. 가비아에서 네임서버 교체

My가비아 > 서비스 관리 > **도메인** > `imprint.asia` **관리** > **네임서버 설정**

- 1차 / 2차 를 위 Cloudflare 값으로 교체
- 기존 가비아 네임서버(`ns.gabia.co.kr`, `ns.gabia.net`, `ns1.gabia.co.kr`)는 **모두 제거**
- 저장 (도메인 소유자 인증을 요구할 수 있다)

가비아 입력 폼이 **IP 주소**를 함께 요구하면 아래를 쓴다. 호스트명만 받는 폼이면
비워 둔다 — Cloudflare NS 는 글루 레코드가 필요 없다.

| 호스트명 | IPv4 |
|---|---|
| `aldo.ns.cloudflare.com` | `108.162.195.248` |
| `maya.ns.cloudflare.com` | `108.162.192.194` |

> 네임서버를 바꾸면 가비아의 DNS 관리(레코드 편집) 기능이 비활성화된다. 정상이다.
> 이후 모든 레코드는 Cloudflare 대시보드에서 관리한다. 도메인 소유·갱신은 가비아 그대로.

### 2-4. 반영 확인

```bash
./cloudflare/check-dns.sh
```

보통 10분~수 시간, `.asia` 는 최대 48시간까지 볼 수 있다.
Cloudflare 대시보드의 zone 상태가 **Active** 가 되면 완료다.
(Cloudflare 는 위임을 감지하면 메일로도 알려준다.)

**Active 가 되기 전에는 4장 이후로 넘어갈 수 없다.** `cloudflared tunnel login` 의
zone 선택 목록에 도메인이 나타나지 않는다.

---

## 3. Access 정책 — 터널보다 먼저

Zero Trust 대시보드(`one.dash.cloudflare.com`)에서 진행한다. **DNS 라우팅 전에 끝낸다.**

### 3-1. 로그인 방법

Settings > Authentication > Login methods.
개인·회사 양쪽에서 쓸 수 있는 것을 고른다. **One-time PIN**(메일로 코드 발송)이
추가 설치가 없어 사내 기기에 가장 무난하다. Google 로그인도 가능하다.

### 3-2. 애플리케이션 생성

Access > Applications > **Add an application** > **Self-hosted**

| 항목 | 값 |
|---|---|
| Application name | `gemma-webui` |
| Session Duration | 회사 기기를 고려해 짧게 — **24시간 이하** |
| Public hostname | subdomain `ai` / domain `imprint.asia` |

### 3-3. 정책 — 화이트리스트만

Policy 이름 `allowed-users`, Action **Allow**.

| Include | Selector | 값 |
|---|---|---|
| | **Emails** | 접속에 쓸 메일 주소를 **명시적으로 나열** |

⚠️ **`Everyone` 이나 `Emails ending in` 같은 광범위 규칙을 쓰지 않는다.**
"인증된 아무나"는 인증이 아니다. 여기를 한 번 잘못 두면 곧바로 공개 노출이다.

MFA 는 Settings > Authentication 또는 정책의 Require 블록에서 활성화한다.

### 3-4. 서비스 토큰 (CLI·자작 앱용)

Access > Service Auth > **Create Service Token**.
발급된 Client ID / Secret 은 **그때 한 번만 표시된다.**

그리고 애플리케이션 정책에 **별도의 Allow 정책**을 하나 더 추가한다 —
Include > **Service Token** > 방금 만든 토큰. 사용자 정책과 섞지 않는다.

### 3-5. Open WebUI 로그인은 유지한다

`WEBUI_AUTH=True` 를 끄지 않는다. Access 만 믿지 않는 이중 방어다.
Access 설정 실수가 곧바로 대화 노출로 이어지지 않게 하는 장치다.

---

## 4. 터널 구축

```bash
./cloudflare/setup-tunnel.sh
```

스크립트가 순서대로 처리한다. **여러 번 실행해도 안전하다.**

| 단계 | 내용 |
|---|---|
| 0 | `cloudflare.env` 로드, 호스트명이 도메인에 속하는지 검사 |
| 1 | 선행 조건 점검 (가입 잠금 · 루프백 바인딩) — 실패 시 DNS 라우팅 자동 생략 |
| 2 | `brew install cloudflared` |
| 3 | `cloudflared tunnel login` → `~/.cloudflared/cert.pem` |
| 4 | `cloudflared tunnel create gemma` → `~/.cloudflared/<UUID>.json` |
| 5 | `config.yml.template` → `cloudflare/config.yml` (chmod 600) |
| 6 | `ingress validate` + catch-all 규칙이 실제로 404 를 내는지 대조 |
| 7 | `cloudflared tunnel route dns` — **확인 프롬프트 후에만 실행** |

변경 없이 상태만 보려면:

```bash
./cloudflare/setup-tunnel.sh --check
./cloudflare/setup-tunnel.sh --skip-dns    # 터널까지만, 공개는 나중에
```

### 노출 범위에 대한 삼중 방어

같은 사고(모델 API 공개)를 세 곳에서 막는다.

1. `setup-tunnel.sh` — `CF_SERVICE_URL` 이 8080/8888 이면 시작 자체를 거부
2. `run-cloudflared.sh` — 기동 전 `config.yml` 을 검사해 8080/8888 이 있으면 종료
3. `status.sh` — 상태 출력에 경고로 노출

`config.yml` 은 git 에 올리지 않는다(`.gitignore`). 터널 ID 와 자격증명 경로가 박힌다.

---

## 5. 수동 확인

```bash
./cloudflare/run-cloudflared.sh          # 포그라운드로 띄운다 (Ctrl-C 로 종료)
```

다른 터미널에서:

```bash
./cloudflare/check-dns.sh
```

기대 결과는 **302 → `*.cloudflareaccess.com`** 이다. 인증 없이 `200` 이 나오면
Access 정책이 붙지 않은 것이므로 **즉시 터널을 내리고** 3장을 다시 본다.

브라우저로 `https://ai.imprint.asia` → Access 로그인 → Open WebUI 로그인 순으로
두 관문을 지나면 정상이다.

---

## 6. 상시 운영 (LaunchAgent)

`config.yml` 이 있을 때만 터널 에이전트가 등록된다.

```bash
./scripts/install-launchagents.sh --reload
launchctl list | grep gemma        # 네 개가 보여야 한다
./scripts/status.sh
```

로그: `~/Library/Logs/gemma/cloudflared.{out,err}.log`

터널만 재시작:

```bash
launchctl kickstart -k "gui/$(id -u)/dev.gemma.cloudflared"
```

---

## 7. 접속 방법

### 브라우저 (개인·사내 공통)

`https://ai.imprint.asia` — Access 인증 후 Open WebUI 로그인.
설치할 것이 없다. 평범한 HTTPS 라 사내 방화벽 통과율이 가장 높다.

### CLI / 자작 앱

Access 서비스 토큰 헤더 + Open WebUI API 키를 함께 보낸다.
웹 검색은 서버 사이드라 포트 3000 하나만 닿으면 동작한다.

```bash
curl https://ai.imprint.asia/api/chat/completions \
  -H "CF-Access-Client-Id: <서비스토큰 ID>" \
  -H "CF-Access-Client-Secret: <서비스토큰 Secret>" \
  -H "Authorization: Bearer <Open WebUI API 키>" \
  -H "Content-Type: application/json" \
  -d '{"model":"<모델 경로>","messages":[{"role":"user","content":"..."}],"features":{"web_search":true}}'
```

**모델 서버(8080)를 직접 부르면 웹 검색이 되지 않는다.** 검색은 Open WebUI 의 기능이다.

---

## 8. 되돌리기 / 비상 차단

노출을 즉시 끊는 순서대로.

```bash
# 1. 터널만 내린다 (가장 빠름 — 즉시 1033/530 이 된다)
launchctl unload ~/Library/LaunchAgents/dev.gemma.cloudflared.plist

# 2. DNS 레코드 삭제 (Cloudflare 대시보드 DNS > ai 레코드 제거)

# 3. 터널 자체를 없앤다
cloudflared tunnel delete gemma
rm -f cloudflare/config.yml
./scripts/install-launchagents.sh --reload
```

네임서버를 가비아로 되돌리는 것은 별개다 — 가비아 관리 화면에서 되돌린다.
Cloudflare zone 을 지우면 `ai.imprint.asia` 는 해석되지 않는다.

---

## 9. 신뢰 경계 (읽고 넘어갈 것)

**Cloudflare 가 TLS 를 종료한다. 질문과 답변 전체가 Cloudflare 가 평문으로 볼 수
있는 지점을 지나간다.** README 의 "검색어는 외부 대행 서비스를 거치지 않는다"와
충돌하며, 사내 접속이라는 목적을 위해 의식적으로 감수한 것이다.

- 공개 호스트명은 DNS·CT 로그에 영구히 남는다. `ai.imprint.asia` 는 되돌릴 수 없다
- Access 설정 실수는 **즉시 공개 노출**이다. SSH 방식은 실수해도 공개되지 않았다 —
  실패 모드의 성격이 다르다
- 회사 기기에서는 복호화된 내용이 그 기기에 보인다. MDM·화면 캡처·키로깅은
  전송 암호화로 막지 못한다
- 회사 기기에서 개인 서버에 접속하는 것이 **사내 정책상 허용되는지**는 별도 확인 사항이다

민감한 대화는 개인 맥북 + Tailscale/SSH 경로(`docs/usage.md`)를 쓴다.
