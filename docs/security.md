# 보안 설정 (Tailscale + SSH)

원칙: 모델 API·Open WebUI는 **루프백에만** 바인딩하고, 원격 접속은 **Tailscale 위 SSH
로컬 포트 포워딩**으로만 허용한다. 공인 인터넷에 SSH·서비스 포트를 노출하지 않는다.

## 1. 바인딩 확인 (루프백 전용)

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN    # 127.0.0.1:8080 만 나와야 함 (MLX)
lsof -nP -iTCP:8888 -sTCP:LISTEN    # 127.0.0.1:8888 만 나와야 함 (SearXNG)
lsof -nP -iTCP:3000 -sTCP:LISTEN    # 127.0.0.1:3000 만 나와야 함 (Open WebUI)
```
`0.0.0.0` 또는 Tailscale IP가 보이면 안 된다. (본 저장소 실행 스크립트는 `--host 127.0.0.1` 고정)

## 2. Tailscale

- Mac mini와 MacBook에 Tailscale GUI 앱 설치 후 **같은 tailnet**에 로그인.
- **Tailscale SSH 서버는 v1에서 사용하지 않는다** (macOS 기본 원격 로그인을 사용).
- Mac mini 호스트명/IP 확인: `tailscale status` → 이 서버는 `taeukkim-macmini` (100.120.74.31).

> ⚠️ **가장 흔한 함정 — 두 기기의 로그인 제공자(provider)가 같아야 한다.**
> Tailscale은 "사람"이 아니라 **로그인한 계정(제공자)** 으로 tailnet을 구분한다.
> 한 기기는 **Google**, 다른 기기는 **"Sign in with Apple"** 로 로그인하면 (Apple ID가 같아도)
> **서로 다른 tailnet**이 되어 상대가 안 보인다. 이 서버는 **Google `dnwndlsdlsi@gmail.com`** 을
> 쓰므로, MacBook도 반드시 **같은 Google 계정**으로 로그인해야 한다.
> 확인: MacBook `tailscale status` 목록에 `taeukkim-macmini`가 보이면 같은 tailnet.

### 접근 정책(ACL) 예시 — Tailscale admin 콘솔

지정 사용자(MacBook)만 Mac mini의 SSH(22)로:
```jsonc
{
  "acls": [
    { "action": "accept", "src": ["dnwndlsdlsi@gmail.com"], "dst": ["taeukkim-macmini:22"] }
  ],
  "ssh": []   // Tailscale SSH 미사용
}
```
- 기기 승인(device approval)과 키 만료 정책도 콘솔에서 설정한다.

## 3. macOS SSH (공개키 전용)

**서버=Mac mini(SSH 받음), 클라이언트=MacBook(SSH 접속·개인키 보관).**

### 3-1. Mac mini: 원격 로그인 켜기
- 시스템 설정 > 일반 > 공유 > **원격 로그인 ON**, 접근 허용 사용자를 `taeuk`로 제한.
- 또는 터미널: `sudo systemsetup -setremotelogin on`
- 확인: MacBook에서 `ssh taeuk@taeukkim-macmini` 시 호스트 지문 프롬프트가 뜨면 도달한 것.

### 3-2. MacBook: 키 생성 + 등록 (⚠️ 키는 클라이언트에서 만든다)
개인키는 **MacBook에** 있어야 한다. Mac mini에는 공개키만 등록된다.
```bash
# MacBook 에서
ssh-keygen -t ed25519 -C "macbook"      # 3번 엔터 (기본 위치, 암호는 선택)
ssh-copy-id taeuk@taeukkim-macmini       # Mac mini 비번 한 번 입력 → 공개키 자동 등록
ssh taeuk@taeukkim-macmini               # 비번 없이 로그인되면 성공
```
> 흔한 실수: 공개키만 Mac mini에 넣고 정작 **MacBook에 매칭되는 개인키가 없으면**
> 계속 `password:`를 묻는다(키 인증 실패 → 비번 폴백). 반드시 `ssh -v ...`의
> `id_rsa/id_ed25519 type -1`(=파일 없음) 여부로 확인. 없으면 위처럼 새로 만든다.
> 여러 MacBook은 각자 키를 만들어 `ssh-copy-id`로 등록하면 `authorized_keys`에 여러 줄로 쌓인다.

### 3-3. 하드닝 (키 로그인 확인 후에!)
`config/sshd_config.d/gemma.conf`를 Mac mini에 설치:
```bash
sudo cp config/sshd_config.d/gemma.conf /etc/ssh/sshd_config.d/gemma.conf
sudo launchctl kickstart -k system/com.openssh.sshd
```
내용(비밀번호 로그인 차단, 공개키 전용):
```
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
AllowUsers taeuk
```
> ⚠️ **모든 사용 기기에서 키 로그인이 되는 걸 확인한 뒤** 적용한다. 안 그러면 잠길 수 있다.

### 3-4. 네트워크
- **공유기에서 22·3000·8080·8888 포트 포워딩 금지**, 공인 IP 인바운드 없음 확인.

## 4. 검증

- 다른 네트워크(휴대전화 핫스팟)에서 `connect-gemma`로 터널이 열린다.
- 터널을 닫으면 MacBook `http://127.0.0.1:<LOCAL_PORT>`(예: 3001) 접근이 즉시 실패한다.
- SSH 터널 없이 Mac mini의 LAN/Tailscale/공인 주소로 3000·8080·8888에 직접 접근되지 않는다.
- MacBook Tailscale을 끄면 터널을 새로 만들 수 없다.
- 비밀번호 SSH 로그인이 거부되고, 등록된 키를 가진 사용자만 접속된다.

## 5. Cloudflare 경로의 신뢰 경계

사내 기기용으로 `https://ai.imprint.asia` 를 연다. 구축 절차는
[remote-access.md](remote-access.md), 여기서는 보안 관점만 정리한다.

**신뢰 경계가 달라진다.** SSH 경로는 종단간 암호화라 중간에 평문을 보는 주체가
없지만, Cloudflare 경로는 **엣지에서 TLS 가 종료된다.** 질문·답변 전체가
Cloudflare 가 평문으로 볼 수 있는 지점을 지나간다. 민감한 대화는 SSH 경로를 쓴다.

지켜야 할 것:

- **노출 범위**: 터널 ingress 에 `127.0.0.1:3000`(Open WebUI) 외에는 넣지 않는다.
  8080(모델 API)·8888(SearXNG)은 인증이 없어 넣는 순간 공개된다.
  `setup-tunnel.sh`·`run-cloudflared.sh`·`status.sh` 세 곳에서 검사하지만,
  최종 책임은 `cloudflare/config.yml` 을 고치는 사람에게 있다.
- **Access 정책은 이메일 화이트리스트만.** `Everyone`, `Emails ending in` 금지.
  "인증된 아무나"는 인증이 아니다.
- **Open WebUI 로그인을 유지한다**(`WEBUI_AUTH=True`). Access 설정 실수 한 번이
  곧바로 대화 노출이 되지 않게 하는 이중 방어다.
- **가입은 잠근다**: `ENABLE_SIGNUP=False`, `DEFAULT_USER_ROLE=pending`.
  공개 접점이 생기면 이 두 값이 유일한 계정 생성 방어선이다.
- **실패 모드가 다르다.** SSH 방식은 설정을 틀려도 공개되지 않지만, Cloudflare 는
  Access 설정 실수가 즉시 공개 노출이다. 공개 호스트명은 CT 로그에 영구히 남는다.
- 비상 차단: `launchctl unload ~/Library/LaunchAgents/dev.gemma.cloudflared.plist`

점검:

```bash
./cloudflare/check-dns.sh    # 인증 없는 요청이 302 → cloudflareaccess.com 이어야 한다
./scripts/status.sh          # ingress 에 8080/8888 이 없는지
```

## 6. 비밀값 취급

- `webui/.env`(WEBUI_SECRET_KEY), SSH 개인키, Tailscale 인증키, API 키는 **커밋 금지**.
  (`.gitignore`에 `webui/.env`, `scripts/connect-gemma.env` 포함)
- Cloudflare: `~/.cloudflared/cert.pem`(계정 인증서)과 `~/.cloudflared/<UUID>.json`
  (터널 자격증명)은 저장소 밖에 있다. `cloudflare/config.yml`·`cloudflare.env` 는
  `.gitignore` 에 있다. Access 서비스 토큰 Secret 은 발급 시 한 번만 표시되며,
  파일로 커밋하지 말고 키체인/비밀번호 관리자에 둔다.
- 대화/추론은 외부 LLM API로 전송되지 않는다. 외부로 나가는 것은 검색어와
  (v1에서는 스니펫만 쓰므로) 검색 엔진 요청뿐이다. 로그로 확인 가능:
  webui 로그에 외부 LLM 호출이 없고 MLX(127.0.0.1)로만 추론 요청이 간다.
