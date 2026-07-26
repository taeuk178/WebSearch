# 보안 설정 (Tailscale + SSH)

원칙: 모델 API·Open WebUI는 **루프백에만** 바인딩하고, 원격 접속은 **Tailscale 위 SSH
로컬 포트 포워딩**으로만 허용한다. 공인 인터넷에 SSH·서비스 포트를 노출하지 않는다.

## 1. 바인딩 확인 (루프백 전용)

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN    # 127.0.0.1:8080 만 나와야 함
lsof -nP -iTCP:3000 -sTCP:LISTEN    # 127.0.0.1:3000 만 나와야 함
```
`0.0.0.0` 또는 Tailscale IP가 보이면 안 된다. (본 저장소 실행 스크립트는 `--host 127.0.0.1` 고정)

## 2. Tailscale

- Mac mini와 MacBook에 Tailscale GUI 앱 설치 후 같은 tailnet에 로그인.
- **Tailscale SSH 서버는 v1에서 사용하지 않는다** (macOS 기본 원격 로그인을 사용).
- Mac mini의 MagicDNS 호스트명 확인: `tailscale status` (예: `mac-mini.tailXXXX.ts.net`).

### 접근 정책(ACL) 예시 — Tailscale admin 콘솔

지정 사용자(MacBook)만 Mac mini의 SSH(22)로:
```jsonc
{
  "acls": [
    { "action": "accept", "src": ["<본인-tailscale-이메일>"], "dst": ["mac-mini:22"] }
  ],
  "ssh": []   // Tailscale SSH 미사용
}
```
- 기기 승인(device approval)과 키 만료 정책도 콘솔에서 설정한다.

## 3. macOS SSH (공개키 전용)

1. 시스템 설정 > 일반 > 공유 > **원격 로그인(SSH) 켜기**. 접근 허용 사용자를 본인으로 제한.
2. 하드닝 — `/etc/ssh/sshd_config.d/gemma.conf` 생성:
   ```
   PasswordAuthentication no
   KbdInteractiveAuthentication no
   PubkeyAuthentication yes
   PermitRootLogin no
   AllowUsers taeuk
   ```
   적용: 원격 로그인 토글 off/on 또는 `sudo launchctl kickstart -k system/com.openssh.sshd`
3. MacBook 공개키를 Mac mini에 등록:
   ```bash
   # MacBook 에서
   ssh-copy-id -i ~/.ssh/id_ed25519.pub taeuk@mac-mini.tailXXXX.ts.net
   ```
4. **공유기에서 22번(및 3000·8080) 포트 포워딩 금지**, 공인 IP 인바운드 없음 확인.

## 4. 검증

- 다른 네트워크(휴대전화 핫스팟)에서 `connect-gemma`로 터널이 열린다.
- 터널을 닫으면 MacBook `http://127.0.0.1:3000` 접근이 즉시 실패한다.
- SSH 터널 없이 Mac mini의 LAN/Tailscale/공인 주소로 3000·8080에 직접 접근되지 않는다.
- MacBook Tailscale을 끄면 터널을 새로 만들 수 없다.
- 비밀번호 SSH 로그인이 거부되고, 등록된 키를 가진 사용자만 접속된다.

## 5. 비밀값 취급

- `webui/.env`(WEBUI_SECRET_KEY), SSH 개인키, Tailscale 인증키, API 키는 **커밋 금지**.
  (`.gitignore`에 `webui/.env`, `scripts/connect-gemma.env` 포함)
- 대화/추론은 외부 LLM API로 전송되지 않는다. 외부로 나가는 것은 검색어와
  (v1에서는 스니펫만 쓰므로) 검색 엔진 요청뿐이다. 로그로 확인 가능:
  webui 로그에 외부 LLM 호출이 없고 MLX(127.0.0.1)로만 추론 요청이 간다.
