# 문제 해결

먼저 `~/gemma-server/scripts/status.sh` 로 전체 상태를 본다.
로그: `~/Library/Logs/gemma/model-server.{out,err}.log`, `webui.{out,err}.log`.

## LaunchAgent가 바로 죽는다 (`launchctl list`에 exit 78/126/-)

- **`Operation not permitted`** (Desktop/Documents/Downloads):
  macOS TCC 보호 폴더에서 실행 중. 저장소를 `~/gemma-server` 등 보호되지 않는 위치로
  옮기고 `./scripts/install-launchagents.sh --reload`.
- 스크립트 실행권한: `chmod +x server/run-model-server.sh webui/run-webui.sh`.
- plist 경로가 틀림: `./scripts/install-launchagents.sh` 재실행(현재 경로로 재생성).

## 모델 로딩 실패

- `model-server.err.log` 확인. 모델 파일 경로/무결성 확인:
  `ls -la ~/gemma-server/models/gemma-4-26b-a4b-it-4bit/*.safetensors`
- mlx 버전 불일치: `server/requirements.lock` 로 재설치.

## 웹 검색이 안 된다 (검색 없이 일반 답변만 나옴)

- **가장 흔한 원인**: 모델 파라미터 `function_calling`이 `legacy`가 아님.
  `gemma4 26b`가 `function_calling=legacy`로 설정됐는지 확인, 아니면 `seed-model.sh` 재실행.
- 입력창 웹 검색 토글이 켜져 있는지 확인.
- `webui/.env`에 `ENABLE_WEB_SEARCH=True`, `WEB_SEARCH_ENGINE=duckduckgo` 확인.
- 자세한 배경: [spike-websearch.md](spike-websearch.md).

## 답변이 비어서 나온다 (사고만 하고 끝남)

- gemma-4의 thinking 채널이 길어 `max_tokens`를 초과. `MAX_TOKENS`를 키우고 재시드.

## 검색은 되는데 특정 URL/공급자 실패

- 개별 URL 실패는 무시되고 나머지로 답한다. 검색 공급자 자체가 실패하면 webui가
  사용자에게 실패를 알리며 서비스는 죽지 않는다. 필요 시 `WEB_SEARCH_ENGINE`을
  SearXNG/Brave/Tavily로 교체(관련 키 설정).

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

- 수동 실행과 LaunchAgent 동시 사용 금지. `lsof -nP -iTCP:8080,3000 -sTCP:LISTEN`로
  중복 프로세스 확인 후 하나만 남긴다.
