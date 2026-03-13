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
    'equipment.apps.EquipmentConfig',
    'soil.apps.SoilConfig',
    'chat',
    'users.apps.UsersConfig',
    'django.contrib.admin',
    "accounts",
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_filters',
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
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
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

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "http")
CSRF_TRUSTED_ORIGINS = ['http://www.s2022.co.kr', 'https://www.s2022.co.kr', 'https://s2022.co.kr', 'http://s2022.co.kr', 'http://211.110.140.201', 'http://211.110.140.201:8001']
LOGIN_REDIRECT_URL = '/'
LANGUAGE_CODE = 'ko-kr'
USE_I18N = True

# 로그인 관련 설정
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'index'
LOGOUT_REDIRECT_URL = 'index'

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
