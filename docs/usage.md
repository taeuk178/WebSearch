# 사용법 (MacBook에서 접속)

## 1. 최초 1회: connect-gemma 설정 (MacBook)

```bash
# 저장소의 scripts/connect-gemma, connect-gemma.env.example 를 MacBook으로 복사
cp scripts/connect-gemma.env.example scripts/connect-gemma.env
# connect-gemma.env 편집: GEMMA_SSH_HOST(=Mac mini Tailscale 호스트명), GEMMA_SSH_USER
# (선택) 어디서나 쓰도록: ln -s "$PWD/scripts/connect-gemma" /usr/local/bin/connect-gemma
```

## 2. 접속

```bash
connect-gemma           # SSH 터널만 연다 (Ctrl-C 로 종료)
connect-gemma --open    # 터널 후 기본 브라우저로 http://127.0.0.1:3000 열기
```

- 터널이 열려 있는 동안 MacBook 브라우저에서 `http://127.0.0.1:3000` 사용.
- 연결이 끊기면 자동 재시도, `Ctrl-C`로 종료하면 터널과 로컬 접근이 함께 닫힌다.
- 전제: Mac mini 전원 ON + 사용자 로그인 + 인터넷 + Tailscale + SSH 정상.

## 3. 웹 검색 (기본 ON)

- 모델은 **`gemma4 26b`** 하나. 기본 답변 언어는 **한국어**(시스템 프롬프트).
- **웹 검색 토글이 기본 ON**이다(웹 검색 전용 사용 목적, 사용자 설정 `ui.webSearch=true`).
  - 매 질문마다 DuckDuckGo에서 최대 5개 결과의 제목·URL·스니펫을 모델에 직접 전달.
  - 답변에 **클릭 가능한 출처**와 인용 번호가 붙는다.
  - 결과가 부족하거나 출처가 상충하면 모델이 그 사실을 밝히고 단정하지 않는다.
- 검색 없이 순수 대화만 하려면 입력창의 웹 검색 토글을 그때만 끈다.
- ⚠️ 검색은 **입력창 토글**로만 켜진다. "검색해줘"라고 글로 써도 토글이 꺼져 있으면 검색되지 않는다.
- **코드 인터프리터/코드 실행은 제거됨**(`ENABLE_CODE_INTERPRETER=False`,
  `ENABLE_CODE_EXECUTION=False`) — 입력창 통합(+) 메뉴에 나타나지 않는다.

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
