# ROADMAP — 운영 패키지 구현 현황

웹 검색 핵심(스파이크)은 검증 완료(`docs/spike-websearch.md`). 아래 항목 대부분이
**구현·검증 완료**되었고, 사용자 수동 작업이 필요한 부분만 남았다. 상세 절차는 `docs/`로 옮겼다.

> 저장소 위치: `~/gemma-server` (TCC 보호 폴더인 `~/Desktop` 등에서는 LaunchAgent 자동 실행 불가).

구현·검증 완료:
- `server/run-model-server.sh` — MLX OpenAI 호환 서버(127.0.0.1:8080)
- `webui/run-webui.sh` + `webui/.env(.example)` — Open WebUI(127.0.0.1:3000), 모델서버 준비 대기 포함
- `webui/seed-model.sh` — 표시명 `gemma4 26b`, `function_calling=legacy`, 한국어 기본 시스템 프롬프트
- 웹 검색 통과: DuckDuckGo + 두 bypass 플래그 + 검색어 생성 OFF, 출처/인용 표시
- 대화 비영속(임시 대화 강제), Arena 모델 숨김
- ✅ **LaunchAgent 자동 실행 + KeepAlive 재시작 실증** (`launchd/*.template`, `scripts/install-launchagents.sh`)
- `scripts/status.sh` 상태 점검, `server|webui/requirements.lock` 버전 잠금
- 문서: `docs/install.md`, `docs/security.md`, `docs/usage.md`, `docs/troubleshooting.md`

실기기 접속 검증 완료(2026-07-26):
- ✅ Mac mini Tailscale(`taeukkim-macmini`, Google `dnwndlsdlsi@gmail.com`) + 원격 로그인 ON
- ✅ MacBook Air(`taeuk-macbookair`)를 **같은 Google 계정**으로 재로그인 → 같은 tailnet
- ✅ 키(공개키) 등록 후 SSH 접속 + `ssh -L` 로컬 포트 포워딩으로 `http://127.0.0.1:3001` → gemma4 접속 성공
- (겪은 함정은 `docs/troubleshooting.md`에 반영: 제공자 불일치, 클라이언트 개인키 부재, 로컬 3000 점유, `-N` 멈춤=정상)

남은 수동 작업:
- SSH **하드닝 미적용**(현재 비밀번호 인증 ON). `config/sshd_config.d/gemma.conf` 준비됨 →
  모든 기기 키 로그인 확인 후 적용 (`docs/security.md` 3-3).
- Tailscale ACL 문서화 적용(선택), 재부팅 후 자동복구 실기기 검증(아래 체크리스트).

---

아래는 각 항목의 설계 근거 원문(참고용). 실제 절차는 위 `docs/`를 따른다.

## 1. macOS 자동 실행/재시작 — LaunchAgent

**목표**: FileVault 유지, 재부팅 후 사용자가 한 번 물리적으로 로그인하면 모델 서버와
Open WebUI가 자동 기동되고, 비정상 종료 시 재시작.
(request: "사용자 로그인 후 LaunchAgent가 … 자동 실행하고 … 다시 시작된다")

**방식**: 시스템 데몬(`/Library/LaunchDaemons`)이 아니라 **사용자 LaunchAgent**
(`~/Library/LaunchAgents`)를 쓴다. 이유:
- MLX는 사용자 GUI 세션의 Metal/GPU 접근이 필요 → 로그인 세션에서 실행해야 함.
- FileVault라서 재부팅 후 어차피 물리 로그인 1회 필요 → 로그인 트리거가 자연스러움.
- ⚠️ 저장소가 TCC 보호 폴더(`~/Desktop` 등)에 있으면 launchd 프로세스가 파일 접근을
  거부당해(`Operation not permitted`) 즉시 죽는다. `~/gemma-server`로 둔다.

**만들 파일** (구현됨, 템플릿):
- `launchd/dev.gemma.model-server.plist.template`
- `launchd/dev.gemma.webui.plist.template`

**plist 핵심 키**:
```

---

## 1. macOS 자동 실행/재시작 — LaunchAgent

**목표**: FileVault 유지, 재부팅 후 사용자가 한 번 물리적으로 로그인하면 모델 서버와
Open WebUI가 자동 기동되고, 비정상 종료 시 재시작.
(request: "사용자 로그인 후 LaunchAgent가 … 자동 실행하고 … 다시 시작된다")

**방식**: 시스템 데몬(`/Library/LaunchDaemons`)이 아니라 **사용자 LaunchAgent**
(`~/Library/LaunchAgents`)를 쓴다. 이유:
- MLX는 사용자 GUI 세션의 Metal/GPU 접근이 필요 → 로그인 세션에서 실행해야 함.
- FileVault라서 재부팅 후 어차피 물리 로그인 1회 필요 → 로그인 트리거가 자연스러움.

**만들 파일**:
- `launchd/dev.gemma.model-server.plist`
- `launchd/dev.gemma.webui.plist`

**plist 핵심 키**:
```
Label            : dev.gemma.model-server  (webui는 dev.gemma.webui)
ProgramArguments : ["/bin/bash", "-lc", "/Users/taeuk/Desktop/WebSearch/server/run-model-server.sh"]
RunAtLoad        : true
KeepAlive        : { SuccessfulExit: false }   # 비정상 종료 시에만 재시작
ThrottleInterval : 10                          # 재시작 폭주 방지
StandardOutPath  : /Users/taeuk/Library/Logs/gemma/model-server.out.log
StandardErrorPath: /Users/taeuk/Library/Logs/gemma/model-server.err.log
ProcessType      : Interactive                 # GPU/Metal 접근
WorkingDirectory : /Users/taeuk/Desktop/WebSearch
```
- webui plist는 위 스크립트를 `run-webui.sh`로, 로그 경로를 webui용으로.
- **의존성**: webui는 모델 서버가 떠야 정상. `KeepAlive`로 각자 재시작하되,
  webui는 `run-webui.sh` 시작부에서 `127.0.0.1:8080/v1/models`를 최대 N초 폴링 후 진행하도록
  가드 추가(모델 서버 준비 대기). 실패해도 KeepAlive가 재시도.

**설치/관리 명령** (문서에 기재):
```
mkdir -p ~/Library/Logs/gemma
cp launchd/*.plist ~/Library/LaunchAgents/
launchctl load  ~/Library/LaunchAgents/dev.gemma.model-server.plist
launchctl load  ~/Library/LaunchAgents/dev.gemma.webui.plist
# 상태: launchctl list | grep gemma
# 해제: launchctl unload ~/Library/LaunchAgents/dev.gemma.*.plist
```
- plist 안의 경로가 사용자 홈에 고정되므로, 재현용으로 `scripts/install-launchagents.sh`를 만들어
  현재 사용자/저장소 경로를 치환해 생성하는 편이 좋다.

**대응 완성 기준**: 재부팅 → 1회 로그인 → 수동 실행 없이 두 서비스 복구.

---

## 2. MacBook `connect-gemma` SSH 터널 명령

**목표**: MacBook에서 `MacBook 127.0.0.1:3000 → Mac mini 127.0.0.1:3000` SSH 로컬 포워딩.
Tailscale 경로로만 SSH 접속. 실패 감지·keepalive·정리.
(request: "connect-gemma … 로컬 포트 포워딩 … 실패 감지 … 연결 유지 … 중단 시 함께 종료")

**만들 파일**: `scripts/connect-gemma` (bash, MacBook에 설치; `/usr/local/bin`에 심볼릭)

**핵심 ssh 옵션**:
```
ssh -N \
  -L 127.0.0.1:3000:127.0.0.1:3000 \
  -o ExitOnForwardFailure=yes \      # 포워딩 실패 시 즉시 종료(=실패 감지)
  -o ServerAliveInterval=15 \        # keepalive
  -o ServerAliveCountMax=3 \
  "$GEMMA_SSH_HOST"                    # Tailscale MagicDNS 호스트명 (예: mac-mini.tailXXXX.ts.net) 또는 tailnet IP
```
- 로컬 3000이 이미 점유면 오류 안내 후 종료.
- `trap 'kill 0' INT TERM EXIT` 로 Ctrl-C 시 터널 정리(연결·로컬 접근 경로 함께 종료).
- 재접속 옵션: `autossh` 대신 간단히 `while` 재시도 루프 + 안내 로그(선택).
- **옵션/별도 명령**: `connect-gemma --open` → 터널 후 `open http://127.0.0.1:3000`
  (기본 브라우저로 Open WebUI 열기).
- 설정값(`GEMMA_SSH_HOST`, `GEMMA_SSH_USER`, 포트)은 `scripts/connect-gemma.env.example`로 분리,
  실제 값은 MacBook 로컬에만 두고 커밋 금지.

**대응 완성 기준**: 다른 네트워크(핫스팟)에서 Tailscale+connect-gemma로 터널 → 브라우저
`http://127.0.0.1:3000` 사용 / 터널 종료 시 즉시 접근 실패 / Tailscale 끄면 터널 생성 불가.

---

## 3. Tailscale + SSH 보안 설정 및 접근 정책

**목표**: 포트를 루프백에만 두고, 원격은 Tailscale 위 SSH 터널로만. 공인 노출 없음.
(request 제약: SSH 공인 미노출, 22 포워딩 금지, 공개키 전용, 지정 사용자만)

**Mac mini 설정 항목** (문서 `docs/security.md`에 절차로):
- Tailscale GUI 앱 설치·로그인, tailnet 연결. **Tailscale SSH 서버는 v1에서 사용 안 함**
  (macOS 기본 원격 로그인 사용).
- 시스템 설정 > 일반 > 공유 > **원격 로그인(SSH) 켜기**, 접근 대상 사용자 지정.
- `/etc/ssh/sshd_config.d/gemma.conf` 로 하드닝:
  ```
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  ChallengeResponseAuthentication no
  PubkeyAuthentication yes
  PermitRootLogin no
  AllowUsers taeuk
  ```
  적용: `sudo launchctl kickstart -k system/com.openssh.sshd` (또는 원격 로그인 토글).
- **공유기에서 22번 포트 포워딩 금지**, 공인 IP 인바운드 없음 확인.
- MacBook 공개키를 Mac mini `~/.ssh/authorized_keys`에 등록. 개인키는 커밋 금지.

**Tailscale ACL(접근 정책) 문서화** (`docs/security.md`에 예시로 기재, 실제는 Tailscale admin):
```jsonc
{
  "acls": [
    // 지정 사용자(MacBook)만 Mac mini의 22(SSH)로
    { "action": "accept", "src": ["user@example.com"], "dst": ["mac-mini:22"] }
  ],
  "ssh": []   // Tailscale SSH 미사용
}
```
- tailnet 태그/기기 승인, 키 만료 정책도 문서에 명시.

**바인딩 확인 명령** (완성 기준 검증용):
```
lsof -nP -iTCP:3000 -sTCP:LISTEN   # 127.0.0.1 만 나와야
lsof -nP -iTCP:8080 -sTCP:LISTEN   # 127.0.0.1 만 나와야  (0.0.0.0 / tailscale IP 금지)
```

**대응 완성 기준**: 루프백 외 바인딩 없음 / 비밀번호 로그인 거부 / 등록 키 사용자만 /
SSH 터널 없이는 LAN·tailnet·공인 어디서도 3000·8080 직접 접근 불가.

---

## 4. 임시 대화(대화 비영속) 설정

**목표**: 계정·보안·버전 등 운영 설정은 보존하되, **대화 내용은 영구 저장하지 않음**.
(request: "채팅을 임시 대화로 사용하여 대화 내용을 영구 저장하지 않는다")

**구현 옵션 검토**:
- Open WebUI에는 채팅별 "임시 채팅(Temporary Chat)" 토글이 있음. 기본을 임시로 강제하는
  전역 스위치가 버전에 따라 제한적 → 다음 중 확인해서 채택:
  - `webui/.env`에 관련 플래그가 있으면 사용(예: 임시 채팅 기본값 관련 설정 존재 여부를
    `open_webui/config.py`에서 grep). 
  - 없으면: 사용자 기본 설정(UserSettings)에서 임시 채팅을 기본 ON으로 seed 하거나,
    사용 지침으로 "항상 임시 채팅 사용"을 문서화 + 주기적 대화 삭제.
- 어느 경우든 **DATA_DIR(계정/설정)은 보존**, 대화 테이블에는 잔류하지 않도록 검증.

**대응 완성 기준**: 임시 대화 종료 후 대화가 기록에 남지 않음.

---

## 5. 상태 점검 / 로그 / 헬스체크

**목표**: 모델 로딩 실패, 검색 실패, SSH 실패, 메모리 부족, 재시작 원인 확인 수단.

**만들 파일**: `scripts/status.sh` (Mac mini에서 실행)
- 포트/바인딩: `lsof -nP -iTCP:8080,3000 -sTCP:LISTEN`
- 헬스: `curl -s 127.0.0.1:8080/v1/models`, `curl -s 127.0.0.1:3000/health`
- LaunchAgent: `launchctl list | grep gemma`
- 메모리: `vm_stat`, `memory_pressure`, 모델 서버 RSS(`ps`)
- 최근 로그 tail: `~/Library/Logs/gemma/*.log`
- Tailscale: `tailscale status`

**로그 위치 정리**(문서화):
- 모델 서버 / webui: `~/Library/Logs/gemma/*.log` (LaunchAgent Std*Path)
- 검색 실패는 webui 로그에서 `Web search`/`WEB_SEARCH_ERROR`로 확인.

**대응 완성 기준**: 각 실패 유형을 로그/명령으로 확인 가능 / 특정 URL·검색 공급자 실패해도
서비스 전체가 죽지 않고 사용자에게 실패 안내(Open WebUI 기본 동작 + 문서 안내).

---

## 6. 문서화

`docs/` 아래 사용자용 문서 4종. 스파이크 문서(`spike-websearch.md`)는 이미 있음.

- `docs/install.md` — 처음부터 재현:
  전제(모델 이미 `models/`에 있음), server venv(3.12)+mlx-lm 설치, webui venv(3.11)+open-webui 설치,
  `.env` 작성(+ `WEBUI_SECRET_KEY` 생성), 최초 관리자 생성, `seed-model.sh`,
  LaunchAgent 설치. **모델 재다운로드 안 함**(경로 고정) 명시.
- `docs/security.md` — 3장 내용(Tailscale/SSH/ACL/바인딩 확인) 절차화.
- `docs/usage.md` — MacBook에서 `connect-gemma`로 접속, 일반 대화 vs 웹 검색 토글,
  출처 확인, 임시 대화 사용, 컨텍스트/출력 한도(초기 16K/2K) 조정 위치.
- `docs/troubleshooting.md` — 모델 로딩 실패, 메모리 부족(컨텍스트→검색 결과 수 순차 축소),
  검색 실패, SSH/터널 실패, 포트 점유, LaunchAgent 재시작 로그 보기.
- 최상위 `README.md` 재작성 — 아키텍처 개요 + 문서 인덱스 + 빠른 시작.

**버전 고정 기록**: `docs/versions.md` 또는 README에
mlx-lm 0.31.3 / mlx 0.32.0 / open-webui 0.10.2 / Python 3.12·3.11 기록,
업데이트 전 회귀 시험(일반 채팅·웹 검색·스트리밍·출처) 절차 명시.
(server/webui 각각 `uv pip freeze > requirements.lock` 로 잠금 파일 남기는 것 권장)

---

## 7. 남은 완성 기준 검증 체크리스트

이미 검증됨(✅) / 실기기·수동 확인 필요(☐):

- [x] LaunchAgent 로드 시 두 서비스 자동 기동 + 강제 종료 시 KeepAlive 재시작 (실증)
- [x] `gemma4 26b`만 노출(Arena 숨김), 로컬 경로 미표시
- [x] 웹 검색 시 서로 다른 출처 5개 + 클릭 가능한 인용 표시
- [x] 일반 대화 시 웹 요청 0, 추가 LLM 호출 없음(대화 1회=MLX 1회)
- [x] 검색 결과 임베딩/벡터 미저장(chroma 컬렉션 없음)
- [x] MacBook Air에서 Tailscale+SSH 터널로 `http://127.0.0.1:3001` → gemma4 접속 성공
- [x] SSH 공개키 로그인 동작(키 등록 후 비밀번호 없이 로그인)
- [ ] 재부팅 → 1회 물리 로그인 → 두 서비스 자동 복구 → 새 터널로 재접속
- [ ] 다른 네트워크(핫스팟)에서 접속 (집 네트워크 외 검증)
- [ ] 터널 종료 시 `http://127.0.0.1:<LOCAL_PORT>` 즉시 실패
- [ ] SSH 터널 없이 LAN/Tailscale/공인으로 3000·8080 직접 접근 불가
- [ ] MacBook Tailscale OFF 시 터널 생성 불가
- [ ] **비밀번호 SSH 거부, 등록 키 사용자만 접속 (하드닝 미적용 — 현재 비번 로그인 가능)**
- [ ] 웹 검색 10회 연속 시 모델 서버 OOM 종료 없음
- [ ] 임시 대화 종료 후 기록 잔류 없음(설정은 강제됨, 실사용 확인)
- [ ] 로그/네트워크 점검으로 프롬프트가 외부 LLM API로 전송되지 않음 확인
- [ ] 웹 검색 질문 5개 첫 토큰 중앙값 측정·기록(목표 30초; 스파이크 단일표본 29.2s)
- [ ] 새 MacBook / 새 Mac mini에서 문서대로 재현
