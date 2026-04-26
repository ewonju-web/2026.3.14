from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")

# 운영 서버에서는 DJANGO_DEBUG=false를 명시하세요.
# 로컬 개발 편의를 위해 환경변수가 없으면 DEBUG=True로 동작합니다.
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = ['211.110.140.201', 's2022.co.kr', 'www.s2022.co.kr', '127.0.0.1', 'localhost']
if DEBUG:
    ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    'django.contrib.sites',  # allauth 필수
    'equipment.apps.EquipmentConfig',
    'soil.apps.SoilConfig',
    'chat',
    'users.apps.UsersConfig',
    'django.contrib.admin',
    "accounts",
    'billing.apps.BillingConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_filters',
    # 소셜 로그인 (카카오/네이버) — 로그인 편의용, 매물/결제 전 휴대폰 인증 별도 필수
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.kakao',
    'allauth.socialaccount.providers.naver',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',

    'django.middleware.locale.LocaleMiddleware',

    # 👇 여기다 넣으세요 (정답 위치)
    'equipment.middleware.visitor_middleware.VisitorCounterMiddleware',

    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'equipment.middleware.admin_session_isolation.AdminSessionIsolationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # ✅ 템플릿 경로를 명시해 줍니다.
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',  # 추가
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # ✅ 방문자 통계 (오늘 / 어제)
                'equipment.context_processors.visitor_stats',
                # 언어(ko/en) 세션 기반
                'chat.context_processors.lang',
                # 채팅 미읽음 총합 (상단 채팅 메뉴 뱃지)
                'chat.context_processors.chat_unread',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

def _env_str(name: str, default: str = "") -> str:
    """dotenv 값에서 감싼 따옴표('"/') 제거."""
    val = os.getenv(name, default)
    if val is None:
        return default
    s = str(val).strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
    # direct-nara(php) 백업 DB: legacy 테이블을 읽어오기 위한 연결
    "legacy": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": _env_str(
            "MYSQL_LEGACY_NAME",
            _env_str("DIRECT_NARA_NAME", "direct_nara_legacy"),
        ),
        "USER": _env_str(
            "MYSQL_LEGACY_USER",
            _env_str("DIRECT_NARA_USER", "root"),
        ),
        "PASSWORD": _env_str(
            "MYSQL_LEGACY_PASSWORD",
            _env_str("DIRECT_NARA_PASSWORD", ""),
        ),
        "HOST": _env_str("MYSQL_LEGACY_HOST", _env_str("DIRECT_NARA_HOST", "127.0.0.1")),
        "PORT": _env_str("MYSQL_LEGACY_PORT", _env_str("DIRECT_NARA_PORT", "3306")),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    },
    # 일부 커맨드가 기대하는 alias(직접 이름: direct_nara)
    "direct_nara": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": _env_str(
            "MYSQL_LEGACY_NAME",
            _env_str("DIRECT_NARA_NAME", "direct_nara_legacy"),
        ),
        "USER": _env_str(
            "MYSQL_LEGACY_USER",
            _env_str("DIRECT_NARA_USER", "root"),
        ),
        "PASSWORD": _env_str(
            "MYSQL_LEGACY_PASSWORD",
            _env_str("DIRECT_NARA_PASSWORD", ""),
        ),
        "HOST": _env_str("MYSQL_LEGACY_HOST", _env_str("DIRECT_NARA_HOST", "127.0.0.1")),
        "PORT": _env_str("MYSQL_LEGACY_PORT", _env_str("DIRECT_NARA_PORT", "3306")),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    },
}

# django-allauth: 소셜 로그인 = 로그인 편의, 휴대폰 인증 = 거래/결제 신뢰 (별도 필수)
SITE_ID = 1
# 운영 도메인 (소셜 로그인 콜백·관리자 "사이트 보기" 등). .env 에 SITE_DOMAIN 으로 덮어쓰기
SITE_DOMAIN = os.getenv('SITE_DOMAIN', 's2022.co.kr')
SITE_NAME = os.getenv('SITE_NAME', '굴삭기나라')
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
ACCOUNT_EMAIL_REQUIRED = False
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_AUTHENTICATION_METHOD = 'username'
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_FORMS = {
    'signup': 'equipment.social_forms.RequiredSocialSignupForm',
}
# 카카오/네이버 키는 Admin > Sites > Social applications 에서 등록하거나, 여기 APP으로 env 설정
# 카카오: https://developers.kakao.com/apps → REST API 키, 리다이렉트: /accounts/kakao/login/callback/
# 네이버: https://developers.naver.com/appinfo → Client ID/Secret, 리다이렉트: /accounts/naver/login/callback/
SOCIALACCOUNT_PROVIDERS = {
    'kakao': {},
    'naver': {},
}
if os.getenv('KAKAO_REST_API_KEY'):
    SOCIALACCOUNT_PROVIDERS['kakao']['APP'] = {
        'client_id': os.getenv('KAKAO_REST_API_KEY'),
        'secret': os.getenv('KAKAO_CLIENT_SECRET', ''),
    }
if os.getenv('NAVER_CLIENT_ID'):
    SOCIALACCOUNT_PROVIDERS['naver']['APP'] = {
        'client_id': os.getenv('NAVER_CLIENT_ID'),
        'secret': os.getenv('NAVER_CLIENT_SECRET', ''),
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

LANGUAGE_CODE = 'ko'
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True
AUTH_USER_MODEL = 'auth.User'

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

# ✅ 미디어 파일 설정 (이게 있어야 사진이 나옵니다)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}

# 인증번호/재발송 제한 등은 멀티워커 환경에서 공유 캐시가 필요합니다.
# 기본 LocMemCache(프로세스별 메모리) 대신 파일 기반 캐시를 사용합니다.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(BASE_DIR / ".django_cache"),
    }
}

USE_X_FORWARDED_HOST = True
# 프록시가 X-Forwarded-Proto: https 일 때만 SSL로 간주. 두 번째 값이 "http"이면 http 요청이 secure로 오인되어 OAuth redirect_uri가 https://로 잘못 생성됨.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# IP 직접·클론(8001)·nginx SSL 종료 시 Origin/Referer가 http 또는 https로 달라질 수 있으므로 둘 다 등록
CSRF_TRUSTED_ORIGINS = [
    'http://www.s2022.co.kr', 'https://www.s2022.co.kr', 'https://s2022.co.kr', 'http://s2022.co.kr',
    'http://211.110.140.201', 'https://211.110.140.201',
    'http://211.110.140.201:8001', 'https://211.110.140.201:8001',
]
_csrf_extra = _env_str("CSRF_TRUSTED_ORIGINS_EXTRA", "")
if _csrf_extra:
    for _part in _csrf_extra.split(","):
        _p = _part.strip()
        if _p and _p not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_p)
LANGUAGE_CODE = 'ko-kr'
USE_I18N = True

# 로그인 관련 설정 (일반 + allauth 소셜 로그인)
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'index'
LOGOUT_REDIRECT_URL = 'index'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# 휴대폰 인증 문자 (equipment.phone_verify_service.send_sms)
# Solapi 연동 (.env)
SOLAPI_API_KEY = _env_str("SOLAPI_API_KEY")
SOLAPI_API_SECRET = _env_str("SOLAPI_API_SECRET")
SOLAPI_SENDER = _env_str("SOLAPI_SENDER")
# 카카오맵 JS SDK 키 (없으면 카카오 로그인 REST 키를 임시로 사용)
KAKAO_MAP_JS_KEY = _env_str("KAKAO_MAP_JS_KEY", _env_str("KAKAO_REST_API_KEY"))

# 비밀번호 찾기 메일: .env에 EMAIL_HOST 있으면 SMTP 발송, 없으면 콘솔 출력
# .env 예시 (실제 발송 시):
#   EMAIL_HOST=smtp.gmail.com
#   EMAIL_PORT=587
#   EMAIL_USE_TLS=true
#   EMAIL_HOST_USER=your-email@gmail.com
#   EMAIL_HOST_PASSWORD=앱비밀번호
#   DEFAULT_FROM_EMAIL=noreply@yourdomain.com
_email_host = os.getenv('EMAIL_HOST', '').strip()
if _email_host:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = _email_host
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@gulsakgi-nara.local')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@gulsakgi-nara.local')
