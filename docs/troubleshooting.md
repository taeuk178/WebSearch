# 문제 해결

먼저 `~/gemma-server/scripts/status.sh` 로 전체 상태를 본다.
로그: `~/Library/Logs/gemma/` 아래 `model-server.{out,err}.log`,
`searxng.{out,err}.log`, `webui.{out,err}.log`.

## LaunchAgent가 바로 죽는다 (`launchctl list`에 exit 78/126/-)

- **`Operation not permitted`** (Desktop/Documents/Downloads):
  macOS TCC 보호 폴더에서 실행 중. 저장소를 `~/gemma-server` 등 보호되지 않는 위치로
  옮기고 `./scripts/install-launchagents.sh --reload`.
- 스크립트 실행권한: `chmod +x server/run-model-server.sh webui/run-webui.sh`.
- plist 경로가 틀림: `./scripts/install-launchagents.sh` 재실행(현재 경로로 재생성).

## 모델 로딩 실패

- `model-server.err.log` 확인. 모델 파일 경로/무결성 확인:
  `ls -la ~/gemma-server/models/Qwen3.6-35B-A3B-4bit/*.safetensors`
- mlx 버전 불일치: `server/requirements.lock` 로 재설치.

## 웹 검색이 안 된다 (검색 없이 일반 답변만 나옴)

- **가장 흔한 원인**: 모델 파라미터 `function_calling`이 `legacy`가 아님.
  `Qwen3.6 35B`가 `function_calling=legacy`로 설정됐는지 확인, 아니면 `seed-model.sh` 재실행.
- 입력창 웹 검색 토글이 켜져 있는지 확인.
- `webui/.env`에 `ENABLE_WEB_SEARCH=True`, `WEB_SEARCH_ENGINE=searxng`,
  `SEARXNG_QUERY_URL=http://127.0.0.1:8888/search` 확인.
- 자세한 배경: [spike-websearch.md](spike-websearch.md).

## "An error occurred while searching the web"

검색 공급자가 결과 0건을 내거나 예외를 던졌다. `webui.err.log`에서
`WEB_SEARCH_ERROR` 또는 `process_web_search`를 찾는다.

- **SearXNG가 안 떠 있음** — `curl -s "127.0.0.1:8888/search?q=test&format=json"`으로 확인.
  죽었으면 `./searxng/run-searxng.sh` 또는 LaunchAgent 재로드.
- **SearXNG의 json 출력이 꺼짐** — `searxng/settings.yml`의 `search.formats`에
  `json`이 있어야 한다. 기본값은 html뿐이라 이게 빠지면 검색이 전혀 동작하지 않는다.
- **엔진이 전부 막힘** — 아래 항목 참조.

> 과거에 `WEB_SEARCH_ENGINE=duckduckgo` + `DDGS_BACKEND` 고정 조합에서 이 오류가
> 재현됐다. `ddgs`가 0건일 때 던지는 `DDGSException`을 Open WebUI가 잡지 않아
> 검색 전체가 400으로 끝난다(`RatelimitException`만 잡는다). 그래서 SearXNG로 옮겼다.

## 검색 결과가 엉뚱하다 / 결과 수가 적다

SearXNG의 어느 엔진이 살아 있는지 본다:
```bash
curl -s "127.0.0.1:8888/search?q=test&format=json" | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('결과', len(d.get('results',[])))
print('실패 엔진', d.get('unresponsive_engines'))"
```
- `CAPTCHA` / `too many requests`가 뜨는 엔진은 차단된 상태다. 기본 활성 엔진 중
  duckduckgo·startpage·brave가 자주 막히며, 현재는 사실상 `google cse` 하나가
  결과를 낸다(ROADMAP 2-4).
- 엔진을 늘리려면 `searxng/settings.yml`에서 `naver`·`mojeek`·`qwant` 등을 활성화한다.
  **켜기 전에 shortcut으로 개별 실측**할 것: `curl -s "127.0.0.1:8888/search?q=!nvr+검색어&format=json"`
- 개별 URL 실패는 무시되고 나머지로 답한다.

## 답변이 비어서 나온다 (추론만 하고 끝남)

thinking이 켜진 상태에서 추론이 `max_tokens`를 다 써버린 경우다.
`finish_reason=length`이고 `content`가 빈 문자열이 된다.

- `MAX_TOKENS`를 키우고 재시드(기본 8192), 또는
- `MLX_THINKING=off`로 서버를 띄운다(기본값). [usage.md](usage.md) 5장 참조.

## 답변이 검색 결과와 어긋난다 / 없는 내용을 지어낸다

- **출처 인용이 붙었는지 먼저 확인한다.** 인용이 없으면 검색 결과에 근거한 답변이
  아니다. 검색이 실패했는데 모델이 자체 지식으로 답한 경우일 수 있다(미해결 문제,
  ROADMAP 3장).
- 모델이 "현재 시점과 맞지 않는 미래 날짜"라며 정상 검색 결과를 의심하면, 답변
  프롬프트에 현재 날짜가 없어 학습 시점을 현재로 착각하는 것이다(미해결).
- 다단계 계산이 틀리면 thinking이 꺼져 있기 때문일 수 있다. [usage.md](usage.md) 5장.

## SSH/터널 실패 (실제로 자주 겪는 순서대로)

**`tailscale status`에 taeukkim-macmini 가 안 보임 / hostname 못 찾음**
- 두 기기의 Tailscale **로그인 제공자가 다름**(가장 흔함). 한쪽 Google, 한쪽 "Sign in with Apple"
  이면 Apple ID가 같아도 다른 tailnet이다. MacBook을 **같은 Google 계정
  (`dnwndlsdlsi@gmail.com`)** 으로 재로그인. → `security.md` 2장.

**`ssh` 가 계속 `password:` 를 물음 (키 인증 실패)**
- MacBook에 **매칭되는 개인키가 없는 것**이 대부분. 확인:
  `ssh -v taeuk@taeukkim-macmini 2>&1 | grep 'type -1'` 에 `id_ed25519/id_rsa type -1`이 뜨면 키 없음.
- 해결(MacBook에서): `ssh-keygen -t ed25519` → `ssh-copy-id taeuk@taeukkim-macmini` → 다시 `ssh`.
- 공개키만 서버에 넣고 개인키가 클라이언트에 없으면 소용없다(공개키·개인키는 한 쌍).

**터널을 열었는데 브라우저가 안 열림**
- `-N` 터널은 접속 후 **커서만 멈춘 게 정상**이다. 비번(또는 키)로 인증만 끝나면 작동 중.
  멈춘 걸 보고 **Ctrl-C 하면 안 된다**(터널 종료됨).
- MacBook **로컬 포트 3000이 이미 점유**면 포워딩이 조용히 실패한다 → `LOCAL_PORT`를 3001로.
  확인: `ssh -v -N -L 3001:127.0.0.1:3000 ...` 로그에 `Local forwarding listening on ... port 3001` 이 떠야 정상.
- 브라우저 주소가 **`http://`** 인지 확인(❌ `https`). Safari 문제면 `http://localhost:3001` 또는 Chrome.

**`오류: Tailscale이 연결되어 있지 않습니다`** → MacBook Tailscale 켜기.

**Mac mini가 응답 없음** → 잠자기 들어갔을 수 있음. 잠자기 해제 또는 `caffeinate -s`.
재부팅 후면 Mac mini에서 한 번 물리 로그인(FileVault) 필요.

## 메모리 부족(OOM) / 서비스 재시작 반복

- `status.sh`의 메모리, `model-server.err.log` 확인.
- 순서대로 축소: 모델 `max_tokens` ↓ → 컨텍스트(프롬프트) ↓ → `WEB_SEARCH_RESULT_COUNT` ↓.
- KeepAlive가 무한 재시작하면 `ThrottleInterval`이 폭주를 막지만, 근본 원인(메모리/모델)을
  로그로 먼저 해결한다.

## 포트 점유/충돌

- 수동 실행과 LaunchAgent 동시 사용 금지. `lsof -nP -iTCP:8080,8888,3000 -sTCP:LISTEN`로
  중복 프로세스 확인 후 하나만 남긴다.

## Cloudflare 원격 접속 (`ai.imprint.asia`)

먼저 `./cloudflare/check-dns.sh` 를 돌린다. 세 단계 중 어디가 깨졌는지 알려준다.
로그: `~/Library/Logs/gemma/cloudflared.{out,err}.log`

**도메인이 아예 해석되지 않는다 (SERVFAIL / NXDOMAIN)**
가비아 네임서버가 아직 Cloudflare 로 바뀌지 않았거나 전파 중이다.
`check-dns.sh` 의 1번 항목 안내를 따른다. `.asia` 는 최대 48시간 걸릴 수 있다.
Cloudflare 대시보드에서 zone 상태가 **Active** 인지 확인한다.

**`cloudflared tunnel login` 목록에 도메인이 없다**
zone 이 아직 Active 가 아니다. 위임 완료를 기다린 뒤 다시 시도한다.

**Error 1033 / 530**
DNS 는 있는데 터널이 엣지에 붙어 있지 않다. cloudflared 가 안 도는 것이다.
```bash
launchctl list | grep cloudflared
tail -30 ~/Library/Logs/gemma/cloudflared.err.log
launchctl kickstart -k "gui/$(id -u)/dev.gemma.cloudflared"
```
`config.yml` 이 없으면 LaunchAgent 는 아예 등록되지 않는다 —
`./cloudflare/setup-tunnel.sh` 를 먼저 돌린다.

**502 / 503 / 504**
터널은 붙었으나 origin(`127.0.0.1:3000`)이 응답하지 않는다. Open WebUI 문제다.
`./scripts/status.sh` 로 WebUI 헬스를 본다.

**인증 없이 200 이 돌아온다 — 가장 위험한 상태**
Access 정책이 이 호스트명에 붙지 않았다. 누구나 접근 가능하다는 뜻이다.
**즉시 터널을 내리고** 원인을 잡는다.
```bash
launchctl unload ~/Library/LaunchAgents/dev.gemma.cloudflared.plist
```
Zero Trust > Access > Applications 에서 도메인이 `ai.imprint.asia` 로 정확히
일치하는지, 정책 Action 이 Allow + Emails 화이트리스트인지 확인한다.

**Access 인증은 되는데 계속 로그인 화면으로 돌아온다**
세션 쿠키 문제다. 시크릿 창으로 재시도하거나
`https://<팀이름>.cloudflareaccess.com/cdn-cgi/access/logout` 으로 로그아웃 후 재로그인.
정책의 이메일 목록에 실제 로그인한 주소가 있는지도 확인한다.

**사내망에서만 연결이 안 된다 / 느리다**
QUIC(UDP 7844)이 막혔을 수 있다. `cloudflare/cloudflare.env` 에서
`CF_PROTOCOL=http2` 로 바꾸고 `./cloudflare/setup-tunnel.sh --skip-dns` 로
config 를 다시 만든 뒤 터널을 재시작한다.

**응답 도중 끊긴다 (524)**
Cloudflare 는 100초 동안 바이트가 전혀 흐르지 않으면 끊는다. 스트리밍 중에는
토큰이 계속 흘러 정상이지만, 첫 토큰이 100초를 넘기면 걸린다.
`MLX_THINKING=off`(기본)인지 확인하고, 컨텍스트가 과도하게 길지 않은지 본다.

**CLI 에서 403 이 난다**
Access 서비스 토큰 헤더(`CF-Access-Client-Id`/`-Secret`)가 빠졌거나, 토큰용
Allow 정책을 애플리케이션에 추가하지 않은 것이다(remote-access.md 3-4).
Open WebUI API 키(`Authorization: Bearer`)와는 **둘 다** 필요하다.
