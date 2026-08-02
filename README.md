# gemma-server — Mac mini 개인용 웹 검색 AI 서버

Mac mini(M4)에서 `mlx-community/Qwen3.6-35B-A3B-4bit`를 MLX로 로컬 실행하고,
Open WebUI로 대화·**실시간 웹 검색**·출처 확인을 제공하는 개인용 서버.
웹 검색은 같은 기기에서 도는 **자체 호스팅 SearXNG**가 담당한다.
외부(MacBook)에서는 Tailscale 위 SSH 로컬 포트 포워딩으로만 접속한다.

> 저장소 이름의 `gemma`는 초기 모델(gemma-4)에서 왔다. 2026-07-31 이후 모델은
> Qwen3.6이며, LaunchAgent 레이블(`dev.gemma.*`)과 로그 경로도 호환을 위해 그대로 둔다.

- 요구사항 원본: [request.md](request.md)
- 웹 검색 호환성 검증 결과: [docs/spike-websearch.md](docs/spike-websearch.md)
- 남은 작업·검증 현황: [ROADMAP.md](ROADMAP.md)

## 아키텍처

접속 경로는 두 가지다. 기본은 SSH 터널이고, 사내 기기용으로 Cloudflare 경로를 둔다.

```
[개인 MacBook] --Tailscale/SSH 터널--> [Mac mini]
  브라우저                              ├─ MLX 모델 서버 (127.0.0.1:8080, OpenAI 호환)
  127.0.0.1:3001  ── SSH -L ──────▶     ├─ SearXNG      (127.0.0.1:8888, 메타서치)
                                        └─ Open WebUI   (127.0.0.1:3000)
[사내 MacBook] --HTTPS 443--▶ Cloudflare      ▲     └─ 검색 스니펫을 프롬프트에 직접 주입
  브라우저                      엣지 + Access ─┘
                                   │        (cloudflared 터널, 3000 만 중계)
                            여기서 TLS 종료
```

- 세 서비스 모두 **`127.0.0.1`에만 바인딩** (LAN/tailnet/공인 미노출).
- SSH 경로: Tailscale 인증 + SSH 공개키. 터널이 열려 있을 때만 사용 가능.
- Cloudflare 경로: `ai.imprint.asia` 하나만 공개. Cloudflare Access(이메일 화이트리스트)
  \+ Open WebUI 로그인의 이중 인증. **8080·8888 은 터널에 넣지 않는다.**
- 검색·대화 내용은 **영구 저장하지 않음**(임시 대화 강제, 스니펫만 메모리 사용).
- 검색어는 외부 대행 서비스를 거치지 않는다. SearXNG가 로컬에서 각 검색엔진에 직접 질의한다.
- ⚠️ 다만 Cloudflare 경로를 쓰면 **대화 전체가 Cloudflare 가 평문으로 볼 수 있는
  지점을 지난다.** 감수한 트레이드오프이며 근거는 [docs/remote-access.md](docs/remote-access.md) 9장.

## 구성요소 (고정 버전)

| | 버전 |
|---|---|
| 모델 | `Qwen3.6-35B-A3B-4bit` (MLX, 19GB) |
| mlx-lm / mlx | 0.31.3 / 0.32.0 |
| open-webui | 0.10.2 |
| SearXNG | 소스 설치 (`searxng/src`, git 미추적) |
| Python | 서버 3.12 · WebUI 3.11 · SearXNG 3.12 (uv) |
| 잠금 파일 | `server/requirements.lock`, `webui/requirements.lock` |

## 모델 선택 근거

Mac mini(M4/32GB)에서 `mlx_lm.benchmark`로 실측한 생성 속도 (생성 256토큰, 3회 평균):

| 프롬프트 토큰 | gemma-4-26b-a4b | **Qwen3.6-35B-A3B** | Qwen3.6 UD(unsloth) |
|---|---|---|---|
| 128 | 38.55 | **45.64** | 30.83 |
| 1,024 | 36.01 | **44.83** | 30.31 |
| 4,096 | 33.78 | **43.31** | 29.81 |
| peak memory | 15.95GB | 21.36GB | 22.59GB |

총 파라미터는 35B로 더 크지만 활성 파라미터가 A3B(3B)라 gemma의 A4B(4B)보다 빠르다.
unsloth의 UD 양자화는 8bit 레이어 비중이 높아 메모리 대역폭에 묶여 48% 느리다.

## 디렉터리

```
server/   MLX 모델 서버 (run-model-server.sh, venv, lock)
searxng/  SearXNG 메타서치 (run-searxng.sh, settings.yml, src·venv·.env 는 git 제외)
webui/    Open WebUI (run-webui.sh, seed-model.sh, .env.example, venv, lock)
cloudflare/ Cloudflare Tunnel (setup-tunnel.sh, check-dns.sh, run-cloudflared.sh;
            config.yml·cloudflare.env 는 git 제외)
launchd/  LaunchAgent plist 템플릿 (자동 실행/재시작)
scripts/  install-launchagents.sh, status.sh, connect-gemma(MacBook)
docs/     install / security / usage / remote-access / troubleshooting / spike-websearch
models/   Qwen3.6-35B-A3B-4bit (19GB, git 제외)
```

## 빠른 시작

1. 설치: [docs/install.md](docs/install.md)
2. 보안(Tailscale/SSH): [docs/security.md](docs/security.md)
3. 사용(MacBook 접속): [docs/usage.md](docs/usage.md)
4. 원격 접속(Cloudflare, 사내 기기용): [docs/remote-access.md](docs/remote-access.md)
5. 문제 해결: [docs/troubleshooting.md](docs/troubleshooting.md)

상태 점검: `./scripts/status.sh`

> ⚠️ 저장소는 `~/gemma-server`에 둔다. `~/Desktop`·`~/Documents`·`~/Downloads`는
> macOS 프라이버시(TCC) 보호 폴더라 LaunchAgent 자동 실행이 차단된다.
