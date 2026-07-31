# 설치

Mac mini(M4, macOS 15+)에서 처음부터 재현하는 절차. 저장소는 **`~/gemma-server`**에 둔다.
(`~/Desktop` 등 TCC 보호 폴더에 두면 LaunchAgent 자동 실행이 차단된다.)

세 서비스를 올린다: **MLX 모델 서버(8080)**, **SearXNG(8888)**, **Open WebUI(3000)**.
전부 `127.0.0.1`에만 바인딩한다.

## 0. 전제

- Homebrew, `uv`, `git` 설치됨.
- 모델 파일이 `~/gemma-server/models/Qwen3.6-35B-A3B-4bit/`에 있음
  (최초 1회만 내려받고 이후 재다운로드하지 않음).

모델을 아직 받지 않았다면:
```bash
cd ~/gemma-server
hf download mlx-community/Qwen3.6-35B-A3B-4bit \
  --local-dir ./models/Qwen3.6-35B-A3B-4bit      # 약 20GB
```

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

`run-model-server.sh`가 서버 기본값으로 박는 값(Open WebUI가 전달하지 않는 것들):
- `top_k=20` — Qwen3.6 저장소 `generation_config.json` 권장값
- `MLX_THINKING=off` — 추론 채널 비활성. 자세한 트레이드오프는 [usage.md](usage.md) 5장

## 2. SearXNG (웹 검색 백엔드)

Docker를 쓰지 않고 소스에서 venv로 설치한다.

```bash
cd ~/gemma-server/searxng
git clone --depth 1 https://github.com/searxng/searxng.git src
uv venv --python 3.12 .venv
uv pip install --python .venv -r src/requirements.txt
uv pip install --python .venv setuptools wheel
uv pip install --python .venv --no-build-isolation -e ./src
```

> `--no-build-isolation`과 `setuptools` 선설치가 필요하다. 없으면 빌드 의존성
> 문제로 설치가 실패한다.

동작 확인:
```bash
./run-searxng.sh &                       # 127.0.0.1:8888
curl -s "127.0.0.1:8888/search?q=test&format=json" | head -c 200
```

- 최초 실행 시 `SEARXNG_SECRET`을 생성해 `searxng/.env`에 저장한다(git 미추적).
- `settings.yml`의 `formats: [html, json]`이 **필수**다. SearXNG 기본값은 html뿐인데
  Open WebUI는 `format=json`으로 질의하므로, 켜지 않으면 검색이 아예 동작하지 않는다.

## 3. Open WebUI

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
# DEFAULT_MODELS 의 /Users/<user>/ 를 실제 사용자명으로 바꾼다.
# 최초 1회 관리자 계정을 만들려면 .env 에서 ENABLE_SIGNUP=True 로 둔다.
```

실행:
```bash
./run-webui.sh &                         # 127.0.0.1:3000 (모델 서버 준비를 자동 대기)
```

## 4. 최초 관리자 계정 + 모델 등록

1. 브라우저에서 `http://127.0.0.1:3000` 접속 → 첫 계정 생성(관리자).
   생성 후 `.env`의 `ENABLE_SIGNUP=False`로 되돌리고 webui 재시작.
2. 관리자 API 키 발급: 설정 > 계정 > API 키.
3. 모델 등록(표시명 `Qwen3.6 35B`, `function_calling=legacy`, 한국어 기본 프롬프트):
   ```bash
   OWUI_TOKEN=<API키> ./webui/seed-model.sh
   ```

> `function_calling=legacy`는 **Legacy 웹 검색 트리거에 필수**다. 이 값이 아니면
> 검색 토글을 켜도 검색이 동작하지 않는다.

## 5. 자동 실행/재시작 (LaunchAgent)

```bash
cd ~/gemma-server
./scripts/install-launchagents.sh        # plist 생성 + load (3개 서비스)
launchctl list | grep gemma              # 2번째 열 0 이면 정상
```

- 로그인 시 자동 실행되고, 비정상 종료 시 재시작된다(KeepAlive).
- FileVault 사용 시 재부팅 후 **1회 물리 로그인**하면 세 서비스가 자동 복구된다.
- 로그: `~/Library/Logs/gemma/*.log`
- 해제: `./scripts/install-launchagents.sh --uninstall`

> 수동 실행(1~3번의 `&`)과 LaunchAgent를 동시에 쓰면 포트가 충돌한다.
> LaunchAgent를 쓰면 수동 프로세스는 종료한다.

> ⚠️ 3개 서비스 기준의 재부팅 자동복구는 **아직 실기기 검증 전이다**
> (2서비스 시절에는 실증됨). [ROADMAP.md](../ROADMAP.md) 0장 참조.

## 6. 확인

```bash
./scripts/status.sh
```
포트 8080·8888·3000이 `127.0.0.1`에만 떠 있고 헬스가 모두 OK면 완료.
다음: [security.md](security.md) → [usage.md](usage.md).
