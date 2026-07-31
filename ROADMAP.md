# ROADMAP — 운영 패키지 구현 현황

웹 검색 핵심(스파이크)은 검증 완료(`docs/spike-websearch.md`).
운영 패키지 대부분이 구현·검증 완료이며, 남은 것은 **실기기 수동 검증**과
**2026-07-31 모델·검색엔진 교체에 따른 재검증**이다. 상세 절차는 `docs/`에 있다.

> 저장소 위치: `~/gemma-server` (TCC 보호 폴더인 `~/Desktop` 등에서는 LaunchAgent 자동 실행 불가).

---

## 0. 지금 해야 할 일 (우선순위)

| # | 항목 | 상태 | 비고 |
|---|---|---|---|
| 0 | **Open WebUI 가입 잠그기** | **미적용** | 현재 누구나 관리자 계정 생성 가능. 원격 노출 전 필수 |
| 1 | SSH 하드닝 적용 | **미적용** | 현재 비밀번호 인증 ON. 보안 모델의 핵심 전제가 깨진 상태 |
| 2 | **Cloudflare 원격 접속 구축** | 착수 전 | 7장에 상세 계획. 사내 맥북 접속 목적 |
| 3 | 재부팅 자동복구 실기기 검증 | 미검증 | SearXNG LaunchAgent 추가 후 3개 서비스 기준으로 재확인 필요 |
| 4 | 웹 검색 토글 실사용 검증 | **미검증** | 아래 4장 참조. 모델·검색엔진이 모두 바뀌어 기존 검증이 무효 |
| 5 | 네트워크 격리 검증 | 미검증 | 핫스팟 접속, 터널 종료 시 차단, 직접 접근 불가 |
| 6 | 성능 재측정 | 미측정 | 첫 토큰 지연·연속 검색 OOM. 모델 교체로 전제가 바뀜 |
| 7 | Tailscale ACL 문서화 적용 | 선택 | `docs/security.md`에 예시 기재됨 |

**0번이 가장 급하다.** `webui/.env` 가 아래 상태다.

```
ENABLE_SIGNUP=True
DEFAULT_USER_ROLE=admin
```

지금은 SSH 터널이 장벽 역할을 해서 실질 위험이 낮지만, 7장의 원격 접속을 열면
**공개 접점에 닿는 누구나 비밀번호도 초대도 없이 관리자 계정을 만들 수 있다.**
`docs/install.md` 에도 "관리자 생성 후 False 로 되돌리라"고 적혀 있으나 되돌려지지
않았다. `ENABLE_SIGNUP=False`, `DEFAULT_USER_ROLE=pending` 으로 고친다.

1번도 같은 성격이다. 이 서버의 보안 모델 전체가 "Tailscale + SSH 공개키 전용"에
의존하는데, 지금은 비밀번호로도 로그인된다. `config/sshd_config.d/gemma.conf`가
준비돼 있고 적용만 남았다. **모든 기기의 키 로그인을 먼저 확인**해야 한다 —
순서를 틀리면 원격 접속이 막힌다. 절차: `docs/security.md` 3-3.

0번과 1번 없이 2번을 먼저 하면 **지금보다 덜 안전해진다.**

---

## 1. 구현·검증 완료

- `server/run-model-server.sh` — MLX OpenAI 호환 서버(127.0.0.1:8080)
- `searxng/run-searxng.sh` + `searxng/settings.yml` — SearXNG 메타서치(127.0.0.1:8888)
- `webui/run-webui.sh` + `webui/.env(.example)` — Open WebUI(127.0.0.1:3000), 모델서버 준비 대기 포함
- `webui/seed-model.sh` — 표시명 `Qwen3.6 35B`, `function_calling=legacy`, 한국어 기본 시스템 프롬프트
- 대화 비영속(임시 대화 강제), Arena 모델 숨김
- LaunchAgent 자동 실행 + KeepAlive 재시작 실증 (`launchd/*.template`, `scripts/install-launchagents.sh`)
  - ⚠️ 실증 시점은 2서비스 기준. SearXNG 추가분은 미검증(위 0장 2번)
- `scripts/status.sh` 상태 점검, `server|webui/requirements.lock` 버전 잠금
- 문서: `docs/install.md`, `docs/security.md`, `docs/usage.md`, `docs/troubleshooting.md`

**실기기 접속 검증 완료(2026-07-26)**
- Mac mini Tailscale(`taeukkim-macmini`, Google `dnwndlsdlsi@gmail.com`) + 원격 로그인 ON
- MacBook Air(`taeuk-macbookair`)를 **같은 Google 계정**으로 재로그인 → 같은 tailnet
- 키 등록 후 SSH 접속 + `ssh -L` 포워딩으로 `http://127.0.0.1:3001` 접속 성공
- 겪은 함정은 `docs/troubleshooting.md`에 반영(제공자 불일치, 클라이언트 개인키 부재,
  로컬 3000 점유, `-N` 멈춤=정상)

---

## 2. 2026-07-31 변경 — 모델·검색엔진 교체

이날 두 가지가 바뀌었고, 그 결과 이전 검증 일부가 **무효**가 되었다.

### 2-1. 모델: gemma-4-26b-a4b → Qwen3.6-35B-A3B

`mlx_lm.benchmark` 실측에서 생성 속도가 25~28% 앞선다(수치는 README 참조).
동반 변경:
- `top_k` 64 → **20** (Qwen3.6 저장소 `generation_config.json` 권장값)
- `max_tokens` 4096 → **8192** (thinking 토큰이 출력 예산을 먼저 소비)
- `MLX_THINKING` 도입, **기본 off**

**thinking off의 트레이드오프** — 웹 검색 요약은 40.4초 → 6.1초로 빨라지고
정확도·인용은 동일했다. 반면 다단계 산술에서 off는 오답, on은 정답이었다.
추론이 필요하면 `MLX_THINKING=on`으로 띄우거나 요청 본문
`chat_template_kwargs`로 요청 단위 덮어쓰기가 가능하다.

### 2-2. 검색: ddgs(DuckDuckGo) → 자체 호스팅 SearXNG

ddgs는 다른 검색엔진을 비공식 스크래핑하는 라이브러리라 제공자 변화에 그대로 깨진다.
실사용에서 두 가지 실패를 겪었다.

1. **무관한 결과** — `backend='auto'`가 호출마다 제공자를 바꾸는데 일부가 엉뚱한 결과를
   냈다. 동일 질의 5회 중 2회 재현.
2. **검색 자체가 죽음** — 위를 고치려 백엔드를 고정했더니, 0건을 반환하는 질의에서
   `DDGSException`이 전파되어 검색이 400 에러로 끝났다. Open WebUI의
   `search_duckduckgo()`는 `RatelimitException`만 잡는다. 이 고정은 되돌렸다.
   더 심각한 건 그 다음이다 — 검색 실패로 컨텍스트가 비면 모델이 추측으로 답한다.
   실제로 영화 「호프」의 줄거리와 출연진을 상세히 지어냈다.

### 2-3. 완성 기준 변경 — 검색어 생성 활성화

`ENABLE_SEARCH_QUERY_GENERATION`을 `False` → **`True`**로 바꿨다.
사용자 발화를 그대로 검색어로 쓰면 대화체 표현이 검색 품질을 크게 깎기 때문이다.

| 질의 | 1위 결과 |
|---|---|
| `나홍진 감독의 호프 영화 물어본거야` | 스포) 호프 불호? 후기 - 무코 |
| `나홍진 호프 영화` | **호프(영화) - 나무위키** |

⚠️ **이 변경으로 기존 완성 기준 하나가 깨졌다.**
"대화 1회 = MLX 1회"였으나, 이제 **검색 시에는 MLX 호출이 2회**다
(검색어 생성 1회 + 답변 1회). 일반 대화는 여전히 1회다.
검색어 생성 호출은 24~32토큰 JSON 출력이라 1.8~2.0초, 총 지연 증가는 질의당 +3.2~4.1초다.
thinking을 꺼둔 덕에 이 비용이 감당 가능한 수준이다.

### 2-4. 검색 엔진 현황 — 사실상 단일 엔진

SearXNG 기본 활성 엔진은 10개지만, 실측 결과 일반 질의에 기여하는 것은 하나뿐이다.
한국어·영어 질의 4건 측정:

| 엔진 | 상태 |
|---|---|
| **google cse** | 정상 — 결과 80건 전부 |
| duckduckgo | CAPTCHA (4/4 실패) |
| startpage | Suspended: CAPTCHA (4/4 실패) |
| brave | too many requests (4/4 실패) |
| wikipedia / wikidata | 활성이나 일반 질의 기여 없음 |

SearXNG로 옮긴 목적이 "여러 엔진 집계로 안정성 확보"인데 지금은 그 이점을 못 얻고
있다. google cse가 막히면 검색이 통째로 멈추는 단일 장애점이다.

**보완 후보** — 51개 엔진이 설치돼 있으나 기본 비활성이다.
- 한국어: `naver` (블로그·카페·뉴스)
- 범용 폴백: `mojeek`(자체 크롤러), `qwant`, `yep`, `bing`, `yahoo`

이 목록은 각 엔진의 성격에 근거한 **예상이며 실측이 아니다.** 실제로 응답할지,
CAPTCHA에 걸리지 않을지는 켜서 재봐야 한다. SearXNG는 `!nvr 검색어` 형태의 shortcut으로
특정 엔진만 지정 호출할 수 있어 검증이 쉽다. **켜기 전에 개별 실측**할 것.

---

## 3. 미해결 문제

- **검색 실패 시 모델이 추측으로 답한다.** 컨텍스트가 비면 모델이 평범한 질문으로 인식한다.
  시스템 프롬프트의 "모르면 인정하라" 지시로는 막지 못했다. 웹 검색 어시스턴트로서
  가장 위험한 실패 모드다.
- **최종 답변 프롬프트에 현재 날짜가 없다.** 모델이 학습 시점을 현재로 착각해,
  검색 결과의 2026년 날짜를 보고 "현재 시점(2024년 기준)과 맞지 않는 미래 날짜라
  자료 오류일 가능성"이라고 답했다. 검색어 생성 프롬프트에는 `Today's date`가
  들어가지만 답변 프롬프트에는 없다. 시드할 때 주입하는 방식이 필요하다
  (하드코딩하면 금방 낡는다).
- **google cse 단일 장애점** (2-4 참조).

---

## 4. 검증 범위 — 웹 검색 토글은 미검증

2026-07-31 작업에서 Open WebUI에 인증할 수단이 없어(관리자 API 키 없음, 브라우저 세션
없음) **웹 검색 토글을 직접 눌러 검증하지 못했다.** 대신 Open WebUI 소스에서 각 단계를
그대로 옮겨 파이프라인을 재현하고, 실행 중인 실제 SearXNG(8888)와 MLX(8080)에 붙여
측정했다.

재현한 것:
- `retrieval/web/searxng.py`의 질의 파라미터·User-Agent·score 정렬
- `utils/middleware.py`의 `get_source_context()` — `<source id="N">` 포맷
- `config.py`의 `DEFAULT_RAG_TEMPLATE`, `DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE`

따라서 다음은 **미검증**이다:
- 웹 검색 토글이 실제로 이 파이프라인을 태우는지
- `function_calling=legacy` 트리거가 Qwen3.6에서 동작하는지
- Open WebUI가 생성된 검색어 여러 개를 어떻게 병합·중복제거하는지
  (재현 시에는 URL 기준으로 임의 중복제거했다)

실제로 2-2의 두 실패는 모두 재현 테스트가 아니라 **브라우저 사용 중에** 드러났다.
재현 방식의 한계를 보여주는 사례이므로, 토글 실사용 검증을 미루지 말 것.

검증 방법은 둘 중 하나다.
- 브라우저에서 직접 토글을 켜고 질의
- 관리자 API 키 발급(설정 > 계정 > API 키) 후 WebUI API로 end-to-end 호출

---

## 5. 완성 기준 체크리스트

검증됨(x) / 실기기·수동 확인 필요(空) / 재검증 필요(!)

- [x] LaunchAgent 로드 시 자동 기동 + 강제 종료 시 KeepAlive 재시작 (2서비스 기준 실증)
- [x] 일반 대화 시 웹 요청 0
- [x] 검색 결과 임베딩/벡터 미저장(chroma 컬렉션 없음)
- [x] MacBook Air에서 Tailscale+SSH 터널로 `http://127.0.0.1:3001` 접속 성공
- [x] SSH 공개키 로그인 동작(키 등록 후 비밀번호 없이 로그인)
- [!] 모델 하나만 노출(Arena 숨김), 로컬 경로 미표시 — 표시명이 `Qwen3.6 35B`로 바뀜, 재확인
- [!] 웹 검색 시 서로 다른 출처 5개 + 클릭 가능한 인용 표시 — 검색엔진 교체로 재검증
- [!] ~~대화 1회 = MLX 1회~~ — **검색 시 2회로 변경됨**(2-3). 기준 자체를 수정함
- [!] 웹 검색 10회 연속 시 모델 서버 OOM 종료 없음 — Qwen이 gemma보다 5GB 더 씀, 재검증
- [!] 웹 검색 질문 5개 첫 토큰 중앙값 측정·기록 — thinking off로 크게 개선 예상, 재측정
- [ ] 재부팅 → 1회 물리 로그인 → **세 서비스** 자동 복구 → 새 터널로 재접속
- [ ] 다른 네트워크(핫스팟)에서 접속 (집 네트워크 외 검증)
- [ ] 터널 종료 시 `http://127.0.0.1:<LOCAL_PORT>` 즉시 실패
- [ ] SSH 터널 없이 LAN/Tailscale/공인으로 3000·8080·8888 직접 접근 불가
- [ ] MacBook Tailscale OFF 시 터널 생성 불가
- [ ] **비밀번호 SSH 거부, 등록 키 사용자만 접속 (하드닝 미적용 — 현재 비번 로그인 가능)**
- [ ] 임시 대화 종료 후 기록 잔류 없음(설계상 강제됨, 실사용 확인)
- [ ] 로그/네트워크 점검으로 프롬프트가 외부 LLM API로 전송되지 않음 확인
- [ ] 새 MacBook / 새 Mac mini에서 문서대로 재현

원격 접속(7장) 관련 검증 항목은 7-6에 따로 두었다.

---

## 6. 설계 근거 (참고용)

실제 절차는 `docs/`를 따른다. 아래는 왜 그렇게 설계했는지에 대한 기록이다.

### 6-1. macOS 자동 실행/재시작 — LaunchAgent

**목표**: FileVault를 유지한 채, 재부팅 후 사용자가 한 번 물리적으로 로그인하면
세 서비스가 자동 기동되고 비정상 종료 시 재시작.

**방식**: 시스템 데몬(`/Library/LaunchDaemons`)이 아니라 **사용자 LaunchAgent**
(`~/Library/LaunchAgents`)를 쓴다.
- MLX는 사용자 GUI 세션의 Metal/GPU 접근이 필요 → 로그인 세션에서 실행해야 한다.
- FileVault라서 재부팅 후 어차피 물리 로그인 1회가 필요하므로 로그인 트리거가 자연스럽다.
- ⚠️ 저장소가 TCC 보호 폴더(`~/Desktop` 등)에 있으면 launchd 프로세스가 파일 접근을
  거부당해(`Operation not permitted`) 즉시 죽는다. `~/gemma-server`에 둔다.

**템플릿**:
- `launchd/dev.gemma.model-server.plist.template` (ProcessType: Interactive — GPU 접근)
- `launchd/dev.gemma.searxng.plist.template` (ProcessType: Background — GPU 미사용)
- `launchd/dev.gemma.webui.plist.template` (ProcessType: Interactive)

**핵심 키**: `RunAtLoad: true`, `KeepAlive: {SuccessfulExit: false}`(비정상 종료 시에만
재시작), `ThrottleInterval: 10`(재시작 폭주 방지), 로그는 `~/Library/Logs/gemma/`.

**기동 순서**: WebUI는 `run-webui.sh` 시작부에서 `127.0.0.1:8080/v1/models`를 최대 30초
폴링한 뒤 진행한다. SearXNG는 순서 의존성이 없다 — Open WebUI가 검색 요청이 실제로
들어올 때만 8888을 호출하므로 셋 중 어느 것이 먼저 떠도 무방하다.

plist 안의 경로가 사용자 홈에 고정되므로 `scripts/install-launchagents.sh`가
현재 사용자·저장소 경로를 치환해 생성한다.

**완성 기준**: 재부팅 → 1회 로그인 → 수동 실행 없이 세 서비스 복구.

### 6-2. MacBook `connect-gemma` SSH 터널

**목표**: `MacBook 127.0.0.1:<LOCAL> → Mac mini 127.0.0.1:3000` SSH 로컬 포워딩.
Tailscale 경로로만 SSH 접속. 실패 감지·keepalive·정리.

**핵심 ssh 옵션**:
```
ssh -N \
  -L 127.0.0.1:3001:127.0.0.1:3000 \
  -o ExitOnForwardFailure=yes \      # 포워딩 실패 시 즉시 종료(=실패 감지)
  -o ServerAliveInterval=15 \        # keepalive
  -o ServerAliveCountMax=3 \
  "$GEMMA_SSH_HOST"
```
- 로컬 포트가 이미 점유면 오류 안내 후 종료.
- `trap 'kill 0' INT TERM EXIT`로 Ctrl-C 시 터널 정리.
- `--open` 옵션 → 터널 후 브라우저 자동 열기.
- 설정값은 `scripts/connect-gemma.env`(git 미추적)로 분리.

**완성 기준**: 다른 네트워크에서 Tailscale+connect-gemma로 터널 → 브라우저 사용 /
터널 종료 시 즉시 접근 실패 / Tailscale 끄면 터널 생성 불가.

### 6-3. Tailscale + SSH 보안

**목표**: 포트를 루프백에만 두고 원격은 Tailscale 위 SSH 터널로만. 공인 노출 없음.

- Tailscale GUI 앱 로그인. **Tailscale SSH 서버는 v1에서 사용하지 않는다**
  (macOS 기본 원격 로그인 사용).
- 시스템 설정 > 일반 > 공유 > 원격 로그인(SSH) 켜기, 접근 대상 사용자 지정.
- `/etc/ssh/sshd_config.d/gemma.conf`로 하드닝(비밀번호 인증 off, 공개키 전용,
  root 금지, `AllowUsers taeuk`). 적용:
  `sudo launchctl kickstart -k system/com.openssh.sshd`.
- **공유기에서 22번 포트 포워딩 금지**, 공인 IP 인바운드 없음 확인.
- MacBook 공개키를 Mac mini `~/.ssh/authorized_keys`에 등록. 개인키는 커밋 금지.

**바인딩 확인**:
```
lsof -nP -iTCP:3000 -sTCP:LISTEN   # 127.0.0.1 만 나와야
lsof -nP -iTCP:8080 -sTCP:LISTEN   # 127.0.0.1 만 나와야
lsof -nP -iTCP:8888 -sTCP:LISTEN   # 127.0.0.1 만 나와야
```

### 6-4. 임시 대화(대화 비영속)

**목표**: 계정·보안·버전 등 운영 설정은 보존하되 대화 내용은 영구 저장하지 않음.

`USER_PERMISSIONS_CHAT_TEMPORARY=True` + `..._ENFORCED=True`로 임시 대화를 강제한다.
`DATA_DIR`(계정/설정)은 보존된다.

### 6-5. 상태 점검 / 로그

`scripts/status.sh`가 포트 바인딩(8080·8888·3000), 헬스체크, LaunchAgent 상태,
메모리, Tailscale, 최근 로그를 한 번에 보여준다.

로그 위치: `~/Library/Logs/gemma/{model-server,searxng,webui}.{out,err}.log`
검색 실패는 webui 로그에서 `Web search` / `WEB_SEARCH_ERROR`로 확인한다.

### 6-6. 버전 고정

mlx-lm 0.31.3 / mlx 0.32.0 / open-webui 0.10.2 / Python 3.12·3.11.
업데이트 전 회귀 시험(일반 채팅·웹 검색·스트리밍·출처)을 거친다.
`uv pip freeze > requirements.lock`로 잠금 파일을 갱신한다.

SearXNG는 소스 클론(`searxng/src`)이라 잠금 파일이 없다. 재현이 필요하면
클론 시점의 커밋 해시를 기록해 둘 것.

---

## 7. 원격 접속 — Cloudflare Tunnel + Access

### 7-1. 목적과 결정

**목적**: 사내 맥북과 개인 맥북에서 **동일한 방법으로** 웹 검색 AI를 쓴다.

현행 방식(Tailscale + SSH 터널)은 회사 기기에서 막힐 가능성이 크다. Tailscale은
VPN·네트워크 확장(Network Extension) 권한을 요구하는데 MDM이 강하게 통제하는
영역이다. "소프트웨어 설치"가 아니라 **권한 등급**이 문제다.

검토한 대안과 탈락 사유:

| 방안 | 회사기기 설치 | 인증 | 내용 경유 | 탈락 사유 |
|---|---|---|---|---|
| Tailscale + SSH (현행) | 필요 (VPN 확장) | SSH 키 | 없음 | 회사 기기에서 설치 불가 가능성 |
| Tailscale Serve | 필요 (VPN 확장) | WebUI 로그인 | 없음 | 위와 동일 |
| VPS + 중첩 SSH (ProxyJump) | 불필요 | SSH 키 | **복호화 불가** | 사내 외부 SSH 차단 시 무력 |
| **Cloudflare Tunnel + Access** | 불필요 | **내장** | Cloudflare | **채택** |
| Tailscale Funnel | 불필요 | 없음 | Tailscale | 인증 부재 |
| 메신저 봇 브리지 | 불필요 | 메신저 계정 | 메신저 사업자 | 프라이버시 이점 없음 |
| 공유기 포트 포워딩 | 불필요 | 없음 | 없음 | 요구사항이 명시적으로 금지 |

**Cloudflare를 택한 이유**는 사내망 호환성이다. 평범한 HTTPS 443 트래픽이라
방화벽 통과율이 가장 높다. VPS 중첩 SSH가 프라이버시 면에서 우수하지만
(중계 서버가 내부 SSH 암호문만 보므로 복호화 불가), 회사가 외부 SSH를 막으면
그대로 무력해진다. 그 위험을 감수하지 않기로 했다.

### 7-2. 감수하기로 한 트레이드오프

**Cloudflare가 TLS를 종료한다. 질문·답변 전체가 그들이 평문으로 볼 수 있는
지점을 지나간다.**

이는 README 의 "검색어는 외부 대행 서비스를 거치지 않는다"와 충돌한다.
같은 이유로 Firecrawl(검색어만 외부 전송)을 보류했는데, 이쪽은 **대화 전체**라
노출 범위가 더 넓다. 사내 접속이라는 목적을 위해 의식적으로 감수하는 것이며,
"모르고 지나간" 사항이 아니다.

부수 위험:
- 공개 호스트명이 DNS·CT 로그에 남는다. Access 설정을 한 번 잘못하면 **즉시
  공개 노출**이다. SSH 방식은 설정 실수해도 공개되지 않는다 — 실패 모드의
  성격이 다르다.
- Cloudflare 계정이 단일 의존점이 된다.
- 회사 기기라면 복호화된 내용이 그 기기에서 보인다. 전송 암호화는 엔드포인트를
  보호하지 못한다(MDM·화면 캡처·키로깅).
- 기술적 안전과 별개로, 회사 기기에서 개인 서버에 접속하는 것이 **사내 정책상
  허용되는지**는 별도 확인 사항이다.

### 7-3. 비용

Cloudflare Tunnel·Access(Zero Trust) 는 개인 사용 규모에서 **무료**다.
실제 비용은 도메인뿐이며, Cloudflare Registrar 는 마크업 없이 원가로 판다
(레지스트리 도매가 + ICANN 수수료 $0.18). 등록가와 갱신가가 같고 첫해 할인이
없어 장기 비용 예측이 쉽다.

| TLD | 연 비용(등록=갱신) |
|---|---|
| **.com** | **약 $10.4** |
| .dev | 약 $10.2 |
| .org | 약 $10.1 (첫해 $7.5) |
| .net | 약 $11.9 |
| .app | 약 $12.2 |
| .io | 약 $45 |

→ **연 1.5만원 안팎**이면 충분하다. `.com` 또는 `.dev` 를 권한다.

주의: 가격은 2026-08 조회 기준이며 레지스트리 정책에 따라 변동한다.
그리고 Cloudflare Registrar 는 **Cloudflare 네임서버 사용이 강제**된다.

### 7-4. 작업 항목

**A. 선행 조건 (원격 노출 전 반드시)**

- [ ] `webui/.env`: `ENABLE_SIGNUP=False`
- [ ] `webui/.env`: `DEFAULT_USER_ROLE=pending`
- [ ] 기존 계정 점검 — 불필요한 관리자 계정 제거 (`webui/data/webui.db` 의 `user` 테이블)
- [ ] SSH 하드닝 적용 (0장 1번)
- [ ] 세 서비스가 `127.0.0.1` 에만 바인딩됐는지 재확인 (`scripts/status.sh`)

**B. 도메인·계정 준비**

- [ ] 도메인 결정 및 구매 (Cloudflare Registrar 권장, 연 $10~12)
- [ ] Cloudflare 계정 생성, 도메인의 네임서버를 Cloudflare 로 위임
- [ ] Zero Trust 대시보드 활성화 (무료 플랜)

**C. Tunnel 구축**

- [ ] Mac mini 에 `cloudflared` 설치 (`brew install cloudflared`)
- [ ] `cloudflared tunnel login` → 인증서 발급
- [ ] 터널 생성 (`cloudflared tunnel create gemma`)
- [ ] **ingress 에 3000 만 등록.** 8080(모델 API)·8888(SearXNG) 은 절대 넣지 않는다.
      하나라도 들어가면 인증 없는 모델 API 가 공개된다
- [ ] DNS 라우팅 (`cloudflared tunnel route dns gemma ai.<도메인>`)
- [ ] 수동 기동으로 접속 확인

예상 `config.yml` 형태:
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/taeuk/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: ai.<도메인>
    service: http://127.0.0.1:3000
  - service: http_status:404      # 그 외 전부 차단
```

**D. Access 정책**

- [ ] Access Application 생성 (도메인: `ai.<도메인>`)
- [ ] 정책을 **지정 이메일 화이트리스트**로 설정. "인증된 아무나" 금지
- [ ] MFA 활성화
- [ ] 세션 수명 설정 (회사 기기 고려해 짧게)
- [ ] CLI·자작 앱용 **서비스 토큰** 발급 (별도 정책으로 분리)
- [ ] Open WebUI 자체 로그인 **유지** — Access 만 믿지 않는다(이중 방어)

**E. 상시 운영**

- [ ] `launchd/dev.gemma.cloudflared.plist.template` 작성
      (SearXNG 용과 동일 구조, `ProcessType: Background`)
- [ ] `scripts/install-launchagents.sh` 의 `LABELS` 에 추가
- [ ] `scripts/status.sh` 에 터널 상태 점검 추가
- [ ] 로그 경로 `~/Library/Logs/gemma/cloudflared.{out,err}.log`

**F. 문서**

- [ ] `docs/remote-access.md` 신설 — 방안 비교, 결정 근거, 구축 절차
- [ ] `docs/usage.md` — 사내/개인 맥북 공통 접속 방법 추가
- [ ] `docs/security.md` — Cloudflare 신뢰 경계와 Access 정책 기재
- [ ] `docs/troubleshooting.md` — 터널 끊김, Access 인증 실패 대응
- [ ] `README.md` — 아키텍처 다이어그램에 외부 접속 경로 반영

### 7-5. CLI·앱에서 쓰기

전송이 열리면 클라이언트는 자유롭게 고를 수 있다. 웹 검색은 서버 사이드라
**포트 3000 하나만 닿으면 동작한다.**

```bash
curl https://ai.<도메인>/api/chat/completions \
  -H "CF-Access-Client-Id: <서비스토큰 ID>" \
  -H "CF-Access-Client-Secret: <서비스토큰 Secret>" \
  -H "Authorization: Bearer <Open WebUI API 키>" \
  -H "Content-Type: application/json" \
  -d '{"model":"<모델 경로>","messages":[...],"features":{"web_search":true}}'
```

`features.web_search` 로 검색이 붙는 것은 소스에서 확인했다
(`utils/middleware.py`, `function_calling=legacy` 조건 — 이미 그렇게 시드돼 있다).

**주의**: 모델 서버(8080)를 직접 부르면 웹 검색이 되지 않는다. 검색은 Open WebUI
의 기능이다.

자작 macOS 앱도 같은 API 를 쓴다. 앱은 평범한 HTTPS 클라이언트라 Tailscale 이
걸리는 네트워크 확장 권한이 필요 없다 — 이 점이 앱 방식의 이점이다. 다만 MDM 이
서명되지 않은 앱 설치 자체를 막는지는 별도 확인이 필요하다.
아직 확인하지 않은 것: 출처·인용이 스트림에 실려 오는 포맷.

### 7-6. 검증 항목

- [ ] 개인 맥북에서 `https://ai.<도메인>` 접속 → Access 인증 → 대화 성공
- [ ] **사내 맥북**에서 동일 절차 성공 (방화벽 통과 확인)
- [ ] 웹 검색 토글 동작 + 출처 인용 표시
- [ ] Access 인증 없이 접근 시 차단되는지 (시크릿 창 / 다른 계정)
- [ ] `https://ai.<도메인>` 외 경로가 404 인지 (ingress catch-all 동작)
- [ ] 8080·8888 이 외부에서 접근 불가인지
- [ ] `curl` + 서비스 토큰으로 CLI 응답 성공
- [ ] Mac mini 재부팅 후 터널 자동 복구
- [ ] 터널 중단 시 접속이 즉시 실패하는지
