# 굴삭기나라 사이트 구조·전략·코드 요약 (AI/개발자용)

Claude 등과 이어서 작업할 때 참고할 **사이트 전체 구조, 전략, 코드 위치** 요약입니다.

---

## 1. 사이트 개요

- **서비스명**: 굴삭기나라 (중고 굴삭기·장비 매물 + 구인구직 + 부품/어태치먼트)
- **기술**: Django 5, SQLite(개발) / MySQL(운영 가능), Bootstrap 5, django-allauth(소셜 로그인)
- **도메인/서버**: s2022.co.kr, 211.110.140.201 (배포 대상)
- **기존 사이트 이관**: direct-nara.co.kr (전화번호·이름·비밀번호) → 현재 사이트로 회원·매물 이관 후 **기존 회원 전환** 흐름 제공

---

## 2. 핵심 전략 (비즈니스·정책)

### 2.1 로그인·회원 구분

| 구분 | 설명 |
|------|------|
| **소셜 로그인** | 카카오/네이버 (편의용). 로그인만 간단하게. |
| **휴대폰 인증** | 거래/결제 신뢰용. **매물·구인·구직·부품 등록 전** 및 **유료 결제 전** 필수. 소셜과 별도. |
| **기존 회원** | direct-nara 이관 회원. `username`이 `legacy_`로 시작. 전화번호로 조회 → 임시 비밀번호 발급 → 로그인 후 **정식 회원 전환**(새 아이디·이메일·비밀번호 설정). |
| **신규 회원** | 카카오/네이버/일반 가입. 가입 시 휴대폰 인증 완료하면 `Profile.phone_verified=True`로 저장해 두고, 매물 등록 시 재인증 생략 가능. |

### 2.2 유료/무료

- **무료**: 한 달 **10건**까지 매물 등록 (삭제해도 당월 건수에 포함). 끌어올리기( bump ) 불가, 재등록 제한(동일 모델·동일 사진 30일).
- **유료(프리미엄)**: 무제한 등록, 첫 화면·우측 배너 노출, "이 판매자 매물 전체 보기", 주 1회 끌어올리기.
- **휴대폰 인증**: 무료/유료 모두 **매물 등록·유료 전환 전** 필수.

### 2.3 휴대폰 인증 정책

- **회원가입/기존 회원 확인**: 휴대폰 입력 → 6자리 인증번호 발송(문자) → 검증 → 인증 성공 시 기존 회원 조회 또는 신규 가입 흐름. (문자 발송은 업체 API 연동 후 실제 발송)
- **저장**: 휴대폰 번호는 **하이픈 제거 후** 저장.
- **재발송**: 30초 이후만 가능. **인증 시도 5회** 초과 시 실패 후 재발송 유도.
- **확장**: 같은 인증을 **매물 등록 전·유료 결제 전** 본인 확인 기초 데이터로도 사용.

---

## 3. 프로젝트 구조 (디렉터리·역할)

```
gulsakgi-nara/
├── config/                    # Django 설정
│   ├── settings.py            # ALLOWED_HOSTS, DB, INSTALLED_APPS, SITE_ID, 소셜/SMS 등
│   └── urls.py                # admin, accounts(allauth), chat, soil, ''→equipment, login/logout/signup 등
├── equipment/                 # 메인 앱 (매물·구인구직·부품·회원·인증)
│   ├── models.py              # Profile, Equipment, JobPost, Part, DeletedListingLog 등
│   ├── views.py               # 대부분의 페이지·API 뷰
│   ├── urls.py                # /, /equipment/*, /account/*, /jobs/*, /parts/* 등
│   ├── forms.py              # EquipmentForm, UserSignupForm 등
│   ├── admin.py               # 회원 상태(기존/신규, 인증, 무료/유료, 매물 수, 결제·신고) 표시
│   ├── premium_utils.py       # 유료 회원 판별, 로테이션/사이드바 목록, 무료 한도
│   ├── phone_verify_service.py # 인증번호 발송/검증(캐시), send_sms() 스텁·연동
│   ├── signals.py             # User 생성 시 Profile 자동 생성
│   └── management/commands/   # import_direct_nara, setup_site 등
├── chat/                      # 1:1 채팅
├── soil/                      # 흙/자재 게시판
├── accounts/                  # 결제·멤버십(선택 사용)
├── templates/
│   ├── base.html              # 공통 레이아웃, 네비, 다국어
│   └── registration/          # 로그인, 회원가입, join_choice, legacy_convert, phone_verify 등
├── docs/                      # 아래 문서들
└── deploy/                    # nginx, gunicorn, install.sh, env.example
```

---

## 4. URL·뷰·역할 (equipment 중심)

| URL (name) | 뷰 | 역할 |
|------------|-----|------|
| `/` | index | 메인 매물 목록, 유료 로테이션/사이드바, 검색·필터 |
| `/account/join/` | join_choice | **회원가입 진입**: 휴대폰 입력 → 인증번호 발송/검증 → 기존 vs 신규 결과 |
| `/account/phone-send/` | phone_send | 인증번호 발송 API (JSON) |
| `/account/phone-verify/` | phone_verify | 인증번호 검증 API (JSON), 성공 시 session['verified_phone'] |
| `/account/join-check/` | join_check | 인증 완료 후 기존 회원 여부 조회 (session 기반), 기존이면 임시 비밀번호 발급 |
| `/account/legacy-convert/` | legacy_convert_intro | 기존 회원 전환 안내 (별도 진입용) |
| `/account/convert/` | legacy_convert | 정식 회원 전환 (새 아이디·이메일·비밀번호), phone_verified 반영 |
| `/account/verify-phone/` | verify_phone_page | 매물 등록 전 등 휴대폰 본인인증 **페이지** (필수 체크 시 리다이렉트) |
| `/login/`, `/logout/` | user_login, user_logout | 일반 로그인 (카카오/네이버 링크는 뷰에서 URL 생성해 전달) |
| `/signup/` | signup | 일반 회원가입 폼; session에 verified_phone 있으면 가입 후 Profile.phone_verified 처리 |
| `/mypage/` | my_page | 마이페이지 (legacy 사용자에게 정식 전환 버튼 노출) |
| `/equipment/create/` | equipment_create | 매물 등록 (휴대폰 인증 필수, 무료 한도·재등록 제한) |
| `/equipment/<id>/bump/` | equipment_bump | 끌어올리기 (유료, 주 1회) |
| `/equipment/author/<id>/` | author_listings | 해당 판매자 매물 전체 (유료 전용) |
| `/jobs/create/`, `/parts/create/` | job_create, part_create | 구인구직·부품 등록 (휴대폰 인증 필수) |

---

## 5. 모델 요약 (equipment)

| 모델 | 용도 |
|------|------|
| **Profile** | User 1:1. user_type(개인/매매상), phone, **phone_verified**, **phone_verified_at**, is_premium, premium_until, **legacy_member_id** |
| **Equipment** | 매물. author(FK User), **last_bumped_at**, **legacy_listing_id** |
| **DeletedListingLog** | 무료 회원 삭제 시 모델명·이미지 해시 저장 → 30일 재등록 제한 |
| **JobPost, Part, PartsShop, Comment** | 구인구직, 부품, 업체, 댓글 |

---

## 6. 설정·환경 변수 (.env)

- `SECRET_KEY`, `DJANGO_DEBUG`
- `SITE_DOMAIN`, `SITE_NAME` (사이트 연결, `python manage.py setup_site`)
- 소셜: `KAKAO_REST_API_KEY`, `NAVER_CLIENT_ID` 등 (또는 Admin → Sites → Social applications)
- SMS: `SMS_API_KEY` 또는 `SENS_SERVICE_KEY` 등 — `phone_verify_service.send_sms()` 연동 시 사용
- 이메일: `EMAIL_HOST` 등 (비밀번호 찾기)

---

## 7. 기존 문서 (상세 참고)

| 문서 | 내용 |
|------|------|
| **docs/DIRECT_NARA_MIGRATION_AND_CONVERSION.md** | direct-nara 이관 절차, 정식 회원 전환, 간편 전환 문구 |
| **docs/PHONE_VERIFY_AND_SMS.md** | 휴대폰 인증 API, 3분/5회/30초 제한, 문자 연동 순서, send_sms() |
| **docs/SOCIAL_LOGIN_AND_PHONE_VERIFY.md** | 소셜 로그인(카카오/네이버) vs 휴대폰 인증 역할, 구글 추가 방법 |
| **docs/ARCHITECTURE.md** | 프로젝트 구조, 매물 검색·필터 포인트 |
| **deploy/README_DEPLOY.md**, **deploy/env.example** | 서버 배포, nginx, gunicorn, 사이트 연결 |

---

## 8. AI에게 이어서 작업 맡길 때 넣을 수 있는 문구 예시

- “회원가입은 `docs/SITE_OVERVIEW_FOR_AI.md`와 `equipment/views.py`의 `join_choice`, `phone_send`, `phone_verify`, `join_check` 흐름을 기준으로 해줘.”
- “휴대폰 인증은 `equipment/phone_verify_service.py`와 `docs/PHONE_VERIFY_AND_SMS.md` 보고, 문자만 실제 업체 API로 연동해줘.”
- “기존 회원 전환은 `legacy_convert` 뷰와 `docs/DIRECT_NARA_MIGRATION_AND_CONVERSION.md` 보고, 문구만 수정해줘.”
- “매물 등록 전 인증은 `_require_phone_verified`와 `verify_phone_page` 쓰고 있어. 이거 기준으로 유료 결제 전에도 같은 인증 쓰게 해줘.”

이 문서를 프로젝트 루트 또는 `docs/` 에 두고, Cursor/Claude와 함께할 때 “지금까지 우리가 만든 사이트 구조·전략·코드”를 이걸로 공유하면 됩니다.
