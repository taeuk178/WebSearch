# 사용법 (MacBook에서 접속)

접속 경로는 두 가지다.

| 경로 | 대상 | 설치 필요 | 문서 |
|---|---|---|---|
| **Tailscale + SSH 터널** | 개인 MacBook | Tailscale(VPN 확장 권한) | 이 문서 1·2장 |
| **Cloudflare (`https://ai.imprint.asia`)** | 사내·개인 공통 | 없음 (브라우저만) | [remote-access.md](remote-access.md) |

개인 기기에서는 SSH 경로를 쓴다. 대화가 Cloudflare 를 지나지 않아 더 안전하다.
Cloudflare 경로는 Tailscale 설치가 막히는 **사내 기기용**이며, 대화 전체가
Cloudflare 가 평문으로 볼 수 있는 지점을 지난다([remote-access.md](remote-access.md) 9장).

---

> 아래는 SSH 경로. 전제(최초 1회): MacBook이 Mac mini와 **같은 Google 계정**으로
> Tailscale 로그인 + **키(비밀번호 없이) SSH 로그인**이 되는 상태.
> (설정: [security.md](security.md) 2·3장)
> 확인: `ssh taeuk@taeukkim-macmini` 가 비번 없이 로그인되면 준비 완료.

## 1. 최초 1회: connect-gemma 설정 (MacBook)

```bash
# 저장소의 scripts/connect-gemma, connect-gemma.env.example 를 MacBook으로 복사
cp scripts/connect-gemma.env.example scripts/connect-gemma.env
# (선택) 어디서나 쓰도록: ln -s "$PWD/scripts/connect-gemma" /usr/local/bin/connect-gemma
```
`connect-gemma.env` 내용(이 서버 기준):
```
GEMMA_SSH_HOST=taeukkim-macmini
GEMMA_SSH_USER=taeuk
LOCAL_PORT=3001      # MacBook 로컬 포트 (3000이 이미 쓰이면 3001 등으로)
REMOTE_PORT=3000     # Mac mini Open WebUI 포트
```

## 2. 접속

```bash
connect-gemma --open    # 터널 열고 기본 브라우저로 http://127.0.0.1:3001 자동 열기
connect-gemma           # 터널만 (직접 브라우저에서 http://127.0.0.1:3001)
```
스크립트 없이 raw 명령으로도 가능:
```bash
ssh -N -L 3001:127.0.0.1:3000 taeuk@taeukkim-macmini   # 이 창은 켜둔 채로
```

- ⚠️ `-N` 터널은 접속 후 **아무 메시지 없이 커서만 멈춘 게 정상**이다(작동 중).
  멈춘 걸 보고 Ctrl-C 하면 터널이 닫힌다. **끝날 때까지 창을 켜둔다.**
- 터널이 열려 있는 동안 MacBook 브라우저에서 `http://127.0.0.1:3001` 사용.
  (❌ `https://` 아님. Safari가 말썽이면 `http://localhost:3001` 또는 Chrome)
- `Ctrl-C`로 종료하면 터널과 로컬 접근이 함께 닫힌다. `connect-gemma`는 끊기면 자동 재접속.
- 전제: Mac mini 전원 ON(+잠자기 꺼짐) + 사용자 로그인 + 인터넷 + Tailscale + SSH 정상.

> Mac mini가 **잠자기**에 들면 접속이 끊긴다. 상시 서버로 쓰려면 시스템 설정에서
> 잠자기를 끄거나(권장) 임시로 `caffeinate -s` 를 실행해 둔다.
> 재부팅했다면 Mac mini에서 **한 번 물리 로그인**하면 서비스가 자동 복구된다.

## 3. 웹 검색 (필요할 때 토글)

- 모델은 **`Qwen3.6 35B`** 하나. 기본 답변 언어는 **한국어**(시스템 프롬프트).
- 최신 정보·사실 확인이 필요하면 입력창의 **웹 검색 토글**을 켜고 질문한다.
  - 같은 기기의 **SearXNG**(127.0.0.1:8888)가 여러 검색엔진에 질의하고,
    최대 5개 결과의 제목·URL·스니펫을 모델에 직접 전달한다.
  - 답변에 **클릭 가능한 출처**와 인용 번호가 붙는다.
  - 결과가 부족하거나 출처가 상충하면 모델이 그 사실을 밝히고 단정하지 않는다.
- 토글 OFF(기본)에서는 웹 요청이 발생하지 않고 모델 자체 지식으로 답한다.
- ⚠️ 검색은 **입력창 토글**로만 켜진다. "검색해줘"라고 글로 써도 토글이 꺼져 있으면 검색되지 않는다.
- **코드 인터프리터/코드 실행은 제거됨**(`ENABLE_CODE_INTERPRETER=False`,
  `ENABLE_CODE_EXECUTION=False`) — 입력창 통합(+) 메뉴에 나타나지 않는다.

**검색어는 모델이 다듬어서 보낸다.** `ENABLE_SEARCH_QUERY_GENERATION=True`라
사용자 발화를 그대로 검색하지 않고, 모델이 먼저 검색어를 뽑는다.
"안녕? 손더게스트는 무슨 내용인지 알려줘" → `손더게스트 뜻과 의미`처럼 정리된다.
대화체 표현이 검색 품질을 크게 깎기 때문이다.

- 대가로 **검색 시 MLX 호출이 2회**가 된다(검색어 생성 + 답변). 일반 대화는 1회.
- 검색어 생성은 24~32토큰 JSON 출력이라 1.8~2.0초, 총 지연 증가는 질의당 +3.2~4.1초.

> 매 요청 자동 검색이 필요하면 전역 Filter로 강제할 수 있으나(부하·지연 증가),
> 이 저장소는 on-demand 토글 방식을 기본으로 한다.

> ⚠️ **검색이 실패하면 모델이 추측으로 답할 수 있다.** 검색 결과가 비면 모델은 그것을
> 평범한 질문으로 인식해 자체 지식으로 답하는데, 이때 사실이 아닌 내용을 그럴듯하게
> 지어낸 사례가 있다. 출처 인용이 없는 답변은 검색 결과에 근거한 것이 아니므로
> **출처가 붙었는지 확인**하고 읽을 것.

## 4. 대화 비영속 (임시 대화)

- 임시 대화가 강제되어(`USER_PERMISSIONS_CHAT_TEMPORARY_ENFORCED=True`) 대화 내용은
  기록에 영구 저장되지 않는다. 계정·설정만 보존된다.

## 5. 추론(thinking) 켜고 끄기

Qwen3.6은 thinking 모델이고, **추론과 최종 답변이 같은 출력 예산을 나눠 쓴다.**
기본은 꺼져 있다(`MLX_THINKING=off`).

| | thinking off (기본) | thinking on |
|---|---|---|
| 웹 검색 요약 | **6.1초** / 60토큰 | 40.4초 / 1,351토큰 |
| 다단계 산술 | **오답** | 정답 |

웹 검색 요약은 추론이 거의 필요 없어 끄는 편이 크게 유리하다. 반면 계산·논리
문제에서는 켜야 정확하다. 켜는 방법은 둘이다.

```bash
# 서버 전체를 추론 모드로 (재시작 필요)
MLX_THINKING=on ./server/run-model-server.sh
```
```bash
# 요청 단위로만 (서버 재시작 불필요)
curl -s 127.0.0.1:8080/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model":"/Users/taeuk/gemma-server/models/Qwen3.6-35B-A3B-4bit",
  "messages":[{"role":"user","content":"..."}],
  "chat_template_kwargs":{"enable_thinking":true}
}'
```

## 6. 컨텍스트/출력 길이 조정

메모리(32GB) 한도 안에서 조정한다.
- 모델 출력 상한: 워크스페이스 모델 `Qwen3.6 35B`의 `max_tokens`
  (또는 `webui/seed-model.sh`의 `MAX_TOKENS` 후 재시드). 기본 8192.
- thinking을 켜면 추론이 이 예산을 먼저 소비한다. 너무 작으면 추론 도중 예산이
  끝나 **최종 답변이 통째로 비어버린다**(`finish_reason=length`).
- 메모리 부족 징후가 있으면 **컨텍스트 → 검색 결과 수** 순으로 줄인다
  (`webui/.env`의 `WEB_SEARCH_RESULT_COUNT`).

## 7. 상태 점검

Mac mini에서:
```bash
~/gemma-server/scripts/status.sh
```
