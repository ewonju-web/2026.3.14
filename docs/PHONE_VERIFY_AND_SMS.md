# 휴대폰 인증 및 문자 발송

회원가입·기존 회원 확인용 휴대폰 인증 기능입니다.  
한 번 만들어 두면 **기존 회원 찾기**, **신규 회원가입**, **매물 등록 전 인증**, **유료 결제 전 인증**까지 같은 인증 데이터로 확장할 수 있습니다.

---

## 1. 구현된 기능

| 항목 | 내용 |
|------|------|
| 인증번호 | 6자리 숫자, 유효시간 3분 |
| 재발송 | 30초 이후에만 가능 (버튼 비활성화 + 안내) |
| 검증 시도 | 5회 초과 시 실패, 안내 후 재발송 유도 |
| 저장 | 휴대폰 번호는 **하이픈 제거 후** 저장 (예: 01012345678) |
| 인증 성공 시 | `session['verified_phone']` 설정 → 기존 회원 조회 → 기존이면 전환 흐름, 신규면 가입 흐름 |
| phone_verified | 기존 회원: 로그인 후 정식 전환 시 Profile에 반영. 신규: 일반 가입 완료 시 Profile에 반영 |

### API

- `POST /account/phone-send/` — 인증번호 발송 (body: `phone`, `csrfmiddlewaretoken`)
- `POST /account/phone-verify/` — 인증번호 검증 (body: `phone`, `code`) → 성공 시 세션에 `verified_phone` 저장
- `POST /account/join-check/` — 인증 완료 후 호출, 세션의 번호로 기존 회원 여부 조회 (JSON)

### UI 문구

- 휴대폰 번호를 입력해주세요 / 기존 회원인지 바로 확인해드릴게요.
- 인증번호 보내기 / 인증번호를 입력해주세요 / 인증 확인
- 아, 기존 회원이시네요 / 처음 방문하셨네요
- 회원 정보를 확인하고 있어요 / 잠시만 기다려주세요
- 30초 후 재발송

---

## 2. 문자 발송 연동 (실제 발송)

문자는 **버튼만 붙이는 것이 아니라**, 문자 업체 API 키 발급·발신번호 등록·서버 연동까지 해야 실제로 발송됩니다.

### 권장 순서

1. **문자 업체 선택** (예: NHN SENS, 알리고, 카카오 비즈메시지, Twilio 등)
2. **계정 생성**
3. **발신번호 등록** (사전 등록 필요)
4. **API 키 발급**
5. **서버 연동** — `equipment/phone_verify_service.py` 의 `send_sms()` 구현
6. **화면 연결** — 이미 연결됨 (인증번호 보내기 → 문자 발송 호출)

### 설정 예시 (.env)

```env
# 예: NHN SENS
SENS_SERVICE_KEY=your-service-key
SENS_ACCESS_KEY=...
SENS_SECRET_KEY=...
SMS_SENDER_PHONE=01012345678

# 또는 알리고 등
SMS_API_KEY=...
SMS_SENDER=...
```

### send_sms() 연동 위치

`equipment/phone_verify_service.py` 의 `send_sms(phone_norm, message)` 함수만 수정하면 됩니다.

- `settings.SMS_API_KEY` 또는 `settings.SENS_SERVICE_KEY` 등이 있으면 해당 업체 API 호출
- 없으면 DEBUG 시 콘솔에 `[SMS 스텁] 수신: ..., 내용: ...` 출력 (실제 발송 없음)

---

## 3. 확장: 매물 등록·유료 결제 전 인증

현재도 매물 등록·구인·구직·부품 등록 전에 `_require_phone_verified()` 로 휴대폰 인증을 요구합니다.  
회원가입 시 인증한 번호는 `Profile.phone` + `Profile.phone_verified = True` 로 저장되므로, **가입 시 한 번 인증하면** 매물 등록 시에는 별도 인증 없이 통과할 수 있습니다.  
유료 결제 전에도 같은 `phone_verified` 플래그를 사용하면 됩니다.

---

## 4. 요약

- **인증 흐름**: 휴대폰 입력 → 인증번호 발송(30초 재발송 제한) → 6자리 입력·검증(5회 제한, 3분 유효) → 인증 성공 시 세션 저장 → 기존/신규 분기 → phone_verified 반영.
- **문자 발송**: 현재는 스텁(콘솔 출력). 실제 발송을 위해 문자 업체 선택 → 발신번호·API 키 준비 → `phone_verify_service.send_sms()` 연동만 하면 됩니다.
