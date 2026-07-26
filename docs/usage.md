# 사용법 (MacBook에서 접속)

> 전제(최초 1회): MacBook이 Mac mini와 **같은 Google 계정**으로 Tailscale 로그인 +
> **키(비밀번호 없이) SSH 로그인**이 되는 상태. (설정: [security.md](security.md) 2·3장)
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

- 모델은 **`gemma4 26b`** 하나. 기본 답변 언어는 **한국어**(시스템 프롬프트).
- 최신 정보·사실 확인이 필요하면 입력창의 **웹 검색 토글**을 켜고 질문한다.
  - DuckDuckGo에서 최대 5개 결과의 제목·URL·스니펫을 모델에 직접 전달.
  - 답변에 **클릭 가능한 출처**와 인용 번호가 붙는다.
  - 결과가 부족하거나 출처가 상충하면 모델이 그 사실을 밝히고 단정하지 않는다.
- 토글 OFF(기본)에서는 웹 요청이 발생하지 않고 모델 자체 지식으로 답한다.
- ⚠️ 검색은 **입력창 토글**로만 켜진다. "검색해줘"라고 글로 써도 토글이 꺼져 있으면 검색되지 않는다.
- **코드 인터프리터/코드 실행은 제거됨**(`ENABLE_CODE_INTERPRETER=False`,
  `ENABLE_CODE_EXECUTION=False`) — 입력창 통합(+) 메뉴에 나타나지 않는다.

> 매 요청 자동 검색이 필요하면 전역 Filter로 강제할 수 있으나(부하·지연 증가),
> 이 저장소는 on-demand 토글 방식을 기본으로 한다.

## 4. 대화 비영속 (임시 대화)

- 임시 대화가 강제되어(`USER_PERMISSIONS_CHAT_TEMPORARY_ENFORCED=True`) 대화 내용은
  기록에 영구 저장되지 않는다. 계정·설정만 보존된다.

## 5. 컨텍스트/출력 길이 조정

메모리(32GB) 한도 안에서 조정한다.
- 모델 출력 상한: 워크스페이스 모델 `gemma4 26b`의 `max_tokens`
  (또는 `webui/seed-model.sh`의 `MAX_TOKENS` 후 재시드).
- gemma-4는 내부 사고(thinking) 토큰을 쓰므로 `max_tokens`가 너무 작으면 답변이
  잘릴 수 있다. 메모리 부족 징후가 있으면 **컨텍스트 → 검색 결과 수** 순으로 줄인다
  (`webui/.env`의 `WEB_SEARCH_RESULT_COUNT`).

## 6. 상태 점검

Mac mini에서:
```bash
~/gemma-server/scripts/status.sh
```
