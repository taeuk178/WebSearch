# 설치

Mac mini(M4, macOS 15+)에서 처음부터 재현하는 절차. 저장소는 **`~/gemma-server`**에 둔다.
(`~/Desktop` 등 TCC 보호 폴더에 두면 LaunchAgent 자동 실행이 차단된다.)

## 0. 전제

- Homebrew, `uv`, `git` 설치됨.
- 모델 파일이 `~/gemma-server/models/gemma-4-26b-a4b-it-4bit/`에 있음
  (최초 1회만 내려받고 이후 재다운로드하지 않음).

## 1. 모델 서버 (MLX)

```bash
cd ~/gemma-server/server
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.lock     # 고정 버전 (mlx-lm 0.31.3)
```

동작 확인:
```bash
./run-model-server.sh &                  # 127.0.0.1:8080
curl -s 127.0.0.1:8080/v1/models
```

## 2. Open WebUI

```bash
cd ~/gemma-server/webui
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -r requirements.lock     # 고정 버전 (open-webui 0.10.2)
```

환경 설정:
```bash
cp .env.example .env
# .env 에서 WEBUI_SECRET_KEY 를 임의 값으로 채운다:
python3 -c "import secrets; print(secrets.token_hex(32))"
# 최초 1회 관리자 계정을 만들려면 .env 에서 ENABLE_SIGNUP=True 로 둔다.
```

실행:
```bash
./run-webui.sh &                         # 127.0.0.1:3000 (모델 서버 준비를 자동 대기)
```

## 3. 최초 관리자 계정 + 모델 등록

1. 브라우저에서 `http://127.0.0.1:3000` 접속 → 첫 계정 생성(관리자).
   생성 후 `.env`의 `ENABLE_SIGNUP=False`로 되돌리고 webui 재시작.
2. 관리자 API 키 발급: 설정 > 계정 > API 키.
3. 모델 등록(표시명 `gemma4 26b`, `function_calling=legacy`, 한국어 기본 프롬프트):
   ```bash
   OWUI_TOKEN=<API키> ./webui/seed-model.sh
   ```

## 4. 자동 실행/재시작 (LaunchAgent)

```bash
cd ~/gemma-server
./scripts/install-launchagents.sh        # plist 생성 + load
launchctl list | grep gemma              # 2번째 열 0 이면 정상
```

- 로그인 시 자동 실행되고, 비정상 종료 시 재시작된다(KeepAlive).
- FileVault 사용 시 재부팅 후 **1회 물리 로그인**하면 두 서비스가 자동 복구된다.
- 로그: `~/Library/Logs/gemma/*.log`
- 해제: `./scripts/install-launchagents.sh --uninstall`

> 수동 실행(1·2번의 `&`)과 LaunchAgent를 동시에 쓰면 포트가 충돌한다.
> LaunchAgent를 쓰면 수동 프로세스는 종료한다.

## 5. 확인

```bash
./scripts/status.sh
```
포트 8080·3000이 `127.0.0.1`에만 떠 있고 헬스가 OK면 완료.
다음: [security.md](security.md) → [usage.md](usage.md).
