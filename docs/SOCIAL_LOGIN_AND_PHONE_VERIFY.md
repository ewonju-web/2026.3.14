# 소셜 로그인 + 휴대폰 본인인증 정책

## 구조 요약

| 구분 | 역할 |
|------|------|
| **소셜 로그인 (카카오/네이버)** | 로그인 편의 — 가입·로그인만 간편하게 |
| **휴대폰 본인인증** | 거래/결제 신뢰 — 매물 등록·유료 결제 전 필수 |

소셜 로그인만으로는 기존 전화번호 기반 매물과 정확히 연결되지 않을 수 있으므로, **매물 등록·구인·구직·부품 등록·유료 결제** 전에는 반드시 휴대폰 본인인증을 받도록 분리했습니다.

---

## 1. 소셜 로그인 (django-allauth)

### 설치

```bash
pip install "django-allauth[socialaccount]"
```

### 설정

- **설정 파일**: `config/settings.py` 에 이미 포함됨  
  - `allauth`, `allauth.account`, `allauth.socialaccount`, `kakao`, `naver`  
  - `AUTHENTICATION_BACKENDS` 에 `AuthenticationBackend` 추가  
  - `SITE_ID = 1`  
- **URL**: `/accounts/` 에 `allauth.urls` 포함 (예: `/accounts/login/` 에서 카카오/네이버 로그인)
- **일반 로그인**: 기존 `/login/` 유지. 로그인 페이지에 **카카오·네이버 버튼 분리** (구글 추가 시 템플릿 주석 해제 + settings 에 provider 추가)

### 카카오 개발자 설정

1. [Kakao 개발자 콘솔](https://developers.kakao.com/apps) 에서 앱 생성
2. **REST API 키** 복사
3. **Redirect URI** 등록:  
   `https://yourdomain.com/accounts/kakao/login/callback/`  
   (로컬: `http://127.0.0.1:8000/accounts/kakao/login/callback/`)
4. Django **Admin → Sites → Social applications** 에서  
   - Provider: **Kakao**  
   - Client id: REST API 키  
   - Sites: 해당 사이트 선택 후 추가

### 네이버 개발자 설정

1. [네이버 개발자 센터](https://developers.naver.com/appinfo) 에서 앱 생성
2. **Client ID**, **Client Secret** 복사
3. **Callback URL** 등록:  
   `https://yourdomain.com/accounts/naver/login/callback/`  
   (로컬: `http://127.0.0.1:8000/accounts/naver/login/callback/`)
4. Django **Admin → Sites → Social applications** 에서  
   - Provider: **Naver**  
   - Client id / Secret 입력  
   - Sites: 해당 사이트 선택 후 추가

### 구글 로그인 추가 방법

1. `config/settings.py` 의 `INSTALLED_APPS` 에 `'allauth.socialaccount.providers.google'` 추가
2. [Google Cloud Console](https://console.cloud.google.com/) 에서 OAuth 2.0 클라이언트 ID 생성, 리다이렉트 URI: `https://도메인/accounts/google/login/callback/`
3. Admin → Sites → Social applications 에서 Provider **Google**, Client id / Secret 등록
4. `templates/registration/login.html` 에서 구글 버튼 부분 `{% comment %}` / `{% endcomment %}` 제거

### 환경 변수 (선택)

Admin 대신 .env 로 쓰려면:

- `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`

---

## 2. 휴대폰 본인인증

### 필수 적용 구간

- **매물 등록** (`/equipment/create/`)
- **구인·구직 글 등록** (`/jobs/create/`)
- **부품 등록** (`/parts/create/`)
- **유료 결제** (결제 진행 뷰에서 동일하게 `_require_phone_verified` 사용)

위 동작 전에 `equipment.views._require_phone_verified(request)` 로 체크하며, 미인증 시 `/account/verify-phone/?next=...` 로 보냅니다.

### DB 필드 (equipment.Profile)

- `phone_verified` (Boolean): 본인인증 완료 여부
- `phone_verified_at` (DateTime, null): 인증 시각

### 현재 구현 상태

- **인증 페이지**: `/account/verify-phone/`  
  - 문구: 소셜 로그인은 편의용, 매물/결제 전 휴대폰 인증 필수
- **실제 인증 API** (NICE, KMC, SMS OTP 등) 는 **미연동**  
  - 연동 전까지는 Admin에서 `Profile.phone_verified = True` 로 테스트
  - **DEBUG 모드** 한정: URL 에 `?test=1` 붙이면 휴대폰 번호만 입력하고 제출 시 `phone_verified=True` 로 저장 (테스트용)

### 실서비스 연동 시

1. NICE 본인인증, KMC, 또는 SMS OTP 등 원하는 인증 수단 선택
2. `/account/verify-phone/` 뷰에서 해당 API 호출 후 성공 시  
   `Profile.phone_verified = True`, `phone_verified_at = now` 저장
3. 운영 환경에서는 `?test=1` 분기 제거 또는 비활성화

---

## 3. 유료 결제 전 인증

유료 전환/결제 뷰를 구현할 때, 결제 진행 직전에 다음을 호출하면 됩니다.

```python
from equipment.views import _require_phone_verified

def payment_view(request):
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '유료 결제를 위해 휴대폰 본인인증이 필요합니다.')
        return redirect_resp
    # ... 결제 진행
```

---

## 4. 요약

- **소셜 로그인**: 카카오/네이버로 로그인 가능, 로그인 편의만 제공
- **휴대폰 인증**: 매물 등록·구인·구직·부품·유료 결제 전 필수, 별도 인증 플로우
- **소셜 = 편의, 휴대폰 인증 = 거래/결제 신뢰** 로 역할을 분리한 구조입니다.
