# 시험 후 NHN 서버 배포 및 도메인 연결 가이드

클론 서버에서 **시험(테스트)**을 마친 뒤, **NHN 서버**에 배포하고 **direct-nara.co.kr** 도메인을 연결해 정상 동작시키는 순서입니다.

---

## 전체 흐름 요약

```
[1] 클론 서버에서 시험 완료
       ↓
[2] NHN 서버 준비 (Python, DB, 웹서버)
       ↓
[3] 코드·DB·미디어 배포
       ↓
[4] 도메인(DNS) 연결
       ↓
[5] SSL·웹서버 설정
       ↓
[6] 정상 동작 확인
```

---

## 1단계: 클론 서버에서 시험

- **현재**: http://211.110.140.201:8001/ (클론)
- **확인할 것**:
  - 매물 등록·수정·삭제, 구인구직, 로그인/회원가입
  - 채팅, 찜, 방문자 수
  - 모바일/PC 화면
- 문제 없으면 **Git 커밋 → 푸시**까지 해 두고, NHN 서버에서는 이 저장소를 clone/pull 해서 사용합니다.

---

## 2단계: NHN 서버 준비

NHN 클라우드/호스팅에서 **서버(인스턴스)** 하나를 사용한다고 가정합니다.

### 2.1 서버 접속

- NHN 콘솔에서 **SSH 접속 정보**(IP, 사용자, 키 또는 비밀번호) 확인
- 터미널에서: `ssh 사용자@NHN서버IP`

### 2.2 필수 설치 (Ubuntu/CentOS 기준)

```bash
# Ubuntu 예시
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx

# Python 3.10+ 권장 (버전 확인: python3 --version)
```

### 2.3 프로젝트 디렉터리

```bash
# 예: /var/www/gulsakgi-nara 또는 NHN에서 안내하는 웹 루트
sudo mkdir -p /var/www/gulsakgi-nara
sudo chown $USER:$USER /var/www/gulsakgi-nara
cd /var/www/gulsakgi-nara
```

### 2.4 DB (선택)

- **SQLite**: 추가 설치 없이 그대로 사용 가능 (소규모 운영).
- **MySQL/PostgreSQL**: NHN에서 DB 서비스를 쓰거나, 같은 서버에 설치 후 `settings.py`에서 해당 엔진으로 설정.

---

## 3단계: 코드·DB·미디어 배포

### 3.1 코드 가져오기

```bash
cd /var/www/gulsakgi-nara
git clone https://github.com/본인계정/gulsakgi-nara.git .
# 또는 이미 clone 되어 있으면
git pull origin main
```

### 3.2 가상환경 + 의존성

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3.3 환경 변수 (.env)

```bash
cp .env.example .env   # 없다면 직접 생성
nano .env
```

**필수로 넣을 값 예시:**

```ini
SECRET_KEY=NHN서버용_긴_랜덤_문자열
DJANGO_DEBUG=false
ALLOWED_HOSTS=direct-nara.co.kr,www.direct-nara.co.kr,NHN서버IP
```

- `ALLOWED_HOSTS`는 아래 4단계에서 도메인 연결 후 **direct-nara.co.kr**, **www.direct-nara.co.kr**, NHN 서버 IP를 포함하도록 합니다. (프로젝트의 `settings.py`에서 이미 이 도메인을 허용하도록 되어 있으면 추가만 하면 됩니다.)

### 3.4 DB 마이그레이션

```bash
source venv/bin/activate
cd /var/www/gulsakgi-nara
python manage.py migrate
python manage.py collectstatic --noinput
```

- 기존 direct-nara DB를 이관했다면 그 DB를 쓰고, 새로 시작하면 SQLite/MySQL 등 새 DB에 위 migrate만 하면 됩니다.

### 3.5 미디어 파일 (기존 사이트에서 이관한 경우)

- 이관한 **업로드/이미지** 폴더를 `MEDIA_ROOT`(예: `media/`)로 복사해 두면 됩니다.

---

## 4단계: 도메인(DNS) 연결

**direct-nara.co.kr** 이 NHN 서버를 바라보도록 DNS를 설정합니다.

### 4.1 도메인 관리 위치 확인

- 도메인을 **NHN**에서 구매·관리하면: NHN 콘솔 → DNS/도메인 메뉴
- 다른 업체(가비아, 카페24 등)에서 관리하면: 해당 업체 DNS 설정

### 4.2 DNS 레코드 설정

| 타입 | 호스트 | 값 | 비고 |
|------|--------|-----|------|
| A | @ | NHN서버IP | direct-nara.co.kr |
| A | www | NHN서버IP | www.direct-nara.co.kr |

- **TTL**: 600~3600 정도로 두고, 나중에 안정화되면 3600 이상으로 조정해도 됩니다.
- 반영까지 **수분~몇 시간** 걸릴 수 있으므로, 다음 단계 전에 `ping direct-nara.co.kr` 로 NHN 서버 IP가 나오는지 확인합니다.

---

## 5단계: 웹서버(Nginx) + Gunicorn + SSL

### 5.1 Gunicorn 서비스 등록

```bash
sudo nano /etc/systemd/system/gunicorn-gulsakgi.service
```

**예시 내용:**

```ini
[Unit]
Description=gunicorn for gulsakgi-nara
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/gulsakgi-nara
ExecStart=/var/www/gulsakgi-nara/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/gunicorn-gulsakgi.sock \
    config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

- `User/Group`은 NHN 서버에서 웹으로 쓰는 계정에 맞게 수정 (예: `ubuntu`, `nhn` 등).
- `WorkingDirectory`, `ExecStart` 경로를 실제 프로젝트 경로에 맞게 수정.

```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-gulsakgi
sudo systemctl start gunicorn-gulsakgi
sudo systemctl status gunicorn-gulsakgi
```

### 5.2 Nginx 설정 (도메인 + SSL)

```bash
sudo nano /etc/nginx/sites-available/gulsakgi-nara
```

**HTTP + HTTPS 예시 (Let’s Encrypt 사용):**

```nginx
server {
    listen 80;
    server_name direct-nara.co.kr www.direct-nara.co.kr;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name direct-nara.co.kr www.direct-nara.co.kr;

    ssl_certificate     /etc/letsencrypt/live/direct-nara.co.kr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/direct-nara.co.kr/privkey.pem;

    location / {
        proxy_pass http://unix:/run/gunicorn-gulsakgi.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/gulsakgi-nara/staticfiles/;
    }
    location /media/ {
        alias /var/www/gulsakgi-nara/media/;
    }
}
```

- SSL 인증서가 아직 없으면, 먼저 **80 포트만** 두고 발급 후 443 블록을 추가해도 됩니다.

### 5.3 SSL 인증서 (Let’s Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d direct-nara.co.kr -d www.direct-nara.co.kr
```

- 안내에 따라 이메일 입력·동의하면 인증서가 발급되고, Nginx에 자동으로 설정되는 경우가 많습니다.  
  위처럼 이미 443 블록을 만들어 두었으면, certbot이 경로만 채워 주는지 확인한 뒤 `sudo nginx -t && sudo systemctl reload nginx` 합니다.

### 5.4 Nginx 활성화 및 재시작

```bash
sudo ln -sf /etc/nginx/sites-available/gulsakgi-nara /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 6단계: Django 설정에서 도메인 허용

프로젝트의 `config/settings.py` 에서 **direct-nara.co.kr** 이 허용되어 있는지 확인합니다.

- **ALLOWED_HOSTS**: `'direct-nara.co.kr'`, `'www.direct-nara.co.kr'`, NHN 서버 IP
- **CSRF_TRUSTED_ORIGINS**: `https://direct-nara.co.kr`, `https://www.direct-nara.co.kr`, `http://...` (테스트용이면 http도 잠시 추가)

이미 문서화된 대로 설정되어 있으면, NHN 서버의 `.env` 에서 `ALLOWED_HOSTS` 를 쓰는 방식이면 동일하게 맞추면 됩니다.

---

## 7단계: 정상 동작 확인

1. **https://direct-nara.co.kr** 접속 → 메인·매물·구인구직 열리는지
2. **로그인/회원가입** 동작
3. **매물 등록·수정·삭제** 동작
4. **이미지/미디어** 노출 여부
5. **모바일**에서 한 번 더 확인

문제가 있으면:

- `sudo journalctl -u gunicorn-gulsakgi -f` 로 앱 로그
- `sudo tail -f /var/log/nginx/error.log` 로 Nginx 로그

를 보면서 원인 파악하면 됩니다.

---

## 요약 체크리스트

| 순서 | 작업 |
|------|------|
| 1 | 클론 서버(211.110.140.201:8001)에서 시험 완료 후 Git 푸시 |
| 2 | NHN 서버에 Python, Nginx, (선택) DB 설치 |
| 3 | 프로젝트 clone/pull, venv, requirements, .env, migrate, collectstatic |
| 4 | DNS에서 direct-nara.co.kr, www → NHN 서버 IP (A 레코드) |
| 5 | Gunicorn 서비스 등록·시작 |
| 6 | Nginx 사이트 설정 + SSL(Let’s Encrypt) |
| 7 | ALLOWED_HOSTS·CSRF_TRUSTED_ORIGINS에 도메인 포함 여부 확인 |
| 8 | https://direct-nara.co.kr 접속·기능 테스트 |

이 순서대로 하면 시험 후 NHN 서버를 사용해 도메인까지 연결하고 정상적으로 사이트를 운영할 수 있습니다.
