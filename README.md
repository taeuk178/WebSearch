# gemma-server — Mac mini 개인용 웹 검색 AI 서버

Mac mini(M4)에서 `mlx-community/gemma-4-26b-a4b-it-4bit`를 MLX로 로컬 실행하고,
Open WebUI로 대화·**실시간 웹 검색**·출처 확인을 제공하는 개인용 서버.
외부(MacBook)에서는 Tailscale 위 SSH 로컬 포트 포워딩으로만 접속한다.

- 요구사항 원본: [request.md](request.md)
- 웹 검색 호환성 검증 결과: [docs/spike-websearch.md](docs/spike-websearch.md)

## 아키텍처

```
[MacBook] --Tailscale/SSH 터널--> [Mac mini]
  브라우저                          ├─ MLX 모델 서버 (127.0.0.1:8080, OpenAI 호환)
  127.0.0.1:3000  ── SSH -L ──▶     └─ Open WebUI    (127.0.0.1:3000)
                                          └─ DuckDuckGo 웹 검색(스니펫 직접 주입)
```

- 모델 API와 Open WebUI는 **`127.0.0.1`에만 바인딩** (LAN/tailnet/공인 미노출).
- 원격 접속은 Tailscale 인증 + SSH 공개키. SSH 터널이 열려 있을 때만 사용 가능.
- 검색·대화 내용은 **영구 저장하지 않음**(임시 대화 강제, 스니펫만 메모리 사용).

## 구성요소 (고정 버전)

| | 버전 |
|---|---|
| mlx-lm / mlx | 0.31.3 / 0.32.0 |
| open-webui | 0.10.2 |
| Python | 서버 3.12 · WebUI 3.11 (uv) |
| 잠금 파일 | `server/requirements.lock`, `webui/requirements.lock` |

## 디렉터리

```
server/   MLX 모델 서버 (run-model-server.sh, venv, lock)
webui/    Open WebUI (run-webui.sh, seed-model.sh, .env.example, venv, lock)
launchd/  LaunchAgent plist 템플릿 (자동 실행/재시작)
scripts/  install-launchagents.sh, status.sh, connect-gemma(MacBook)
docs/     install / security / usage / troubleshooting / spike-websearch
models/   gemma-4-26b-a4b-it-4bit (14GB, git 제외)
```

## 빠른 시작

1. 설치: [docs/install.md](docs/install.md)
2. 보안(Tailscale/SSH): [docs/security.md](docs/security.md)
3. 사용(MacBook 접속): [docs/usage.md](docs/usage.md)
4. 문제 해결: [docs/troubleshooting.md](docs/troubleshooting.md)

상태 점검: `./scripts/status.sh`

> ⚠️ 저장소는 `~/gemma-server`에 둔다. `~/Desktop`·`~/Documents`·`~/Downloads`는
> macOS 프라이버시(TCC) 보호 폴더라 LaunchAgent 자동 실행이 차단된다.
