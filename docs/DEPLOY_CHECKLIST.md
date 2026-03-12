# 배포·수정 반영 체크리스트

템플릿/파이썬 수정 후 화면이 **“안 바뀐 것처럼”** 보일 때 확인할 항목입니다.

---

## 0) 워크플로: 클론 → GitHub → 원본 서버

**서버 경로 구분**

- **원본 서버**: `/srv/excavator` (원본 앱 루트)
- **클론 서버**: `/srv/excavator/gulsakgi-nara` (gulsakgi-nara 개발/테스트용)

**지금까지 사용한 흐름**

1. **클론 서버**에서 개발/수정 (예: 211.110.140.201:8001, `/srv/excavator/gulsakgi-nara`)
2. 작업 완료 후 **Git 커밋 → GitHub 푸시**
3. **원본 서버**에서 `git pull` 후 서비스 재시작으로 반영

**원본 서버에 적용할 때 (요약)**

```bash
# 원본 서버에서 (앱 경로는 원본 구성에 맞게)
cd /srv/excavator   # 원본 서버 앱 루트
git pull origin main
# DB 마이그레이션이 있으면
python manage.py migrate
sudo systemctl restart gunicorn   # 원본용 gunicorn 서비스명
# 필요 시
sudo systemctl restart nginx
```

**지금까지 이 흐름으로 반영한 작업 예시**

- 매물 등록 UX(필수/선택 필드, "모름" 표시, 삭제 후 목록 유지)
- 차량번호 필드 및 "번호등록" 뱃지
- 기종 선택 버튼 UI·사진 필수 검증
- PC 첫화면 검색/카테고리 영역 정리
- 1:1 채팅(DB 기반), 언어 선택(ko/en)
- 채팅: set_language `next` 보안, ChatRoom 중복 방지, 미읽음 뱃지, 판매자/구매자 라벨, 메시지 XSS 방지
- 상세페이지 2컬럼 레이아웃, CTA 순서(연락처→채팅→찜→복사), 채팅 빈 상태 문구

---

## 0-1) 클론 서버 최초 설정 (최초 1회, `/srv/excavator/gulsakgi-nara`)

**서버(211.110.140.201 등)에서** 아래 순서로 실행합니다.

```bash
# 1) 디렉터리 이동 후 클론 (원본 /srv/excavator 아래에 클론)
cd /srv/excavator
sudo git clone git@github.com:ewonju-web/gulsakgi-nara.git gulsakgi-nara
cd gulsakgi-nara

# 2) 가상환경 생성 및 의존성 설치
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3) 환경 변수/설정 (원본 서버와 동일한 .env 등 필요 시 복사)
# cp /srv/excavator/.env .env   # 예시

# 4) DB 마이그레이션
python manage.py migrate

# 5) gunicorn·nginx 설정
# - gunicorn 서비스명: gunicorn-gulsakgi-clone (포트 8001 등으로 원본과 분리)
# - nginx에서 8001 포트로 프록시 설정 후:
sudo systemctl enable gunicorn-gulsakgi-clone
sudo systemctl start gunicorn-gulsakgi-clone
sudo systemctl restart nginx
```

**이미 클론만 해 둔 경우** (코드만 최신으로 맞추기):

```bash
cd /srv/excavator/gulsakgi-nara
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
sudo systemctl restart gunicorn-gulsakgi-clone
sudo systemctl restart nginx
```

---

## 1) 클론 반영 확인 (8001이 클론인지)

- **클론 접속**: http://211.110.140.201:8001/
- 수정한 코드가 **클론 경로** (`/srv/excavator/gulsakgi-nara`)에 적용되었는지 확인
- 수정 후에도 변경이 안 보이면 URL 뒤에 **캐시 무효화** 파라미터 추가:  
  `?v=123` 또는 `?t=20250101` 등

---

## 2) 서비스 재시작 (클론)

템플릿/파이썬 수정 후 반영이 안 보이면 아래 순서로 재시작합니다.

```bash
sudo systemctl restart gunicorn-gulsakgi-clone
sudo systemctl restart nginx
```

- **gunicorn**: 애플리케이션 코드/템플릿 로드
- **nginx**: 설정 변경 시 필요 (정적/프록시 등)

---

## 3) 모바일 캐시

- 휴대폰에서는 **시크릿 모드**로 접속하거나 **강력 새로고침** 사용
- 또는 주소에 **쿼리 붙여서** 접속:  
  `http://211.110.140.201:8001/equipment/create/?v=123`

---

## 요약

| 구분       | 경로 / 주소 |
|------------|--------------|
| 원본 서버  | `/srv/excavator` |
| 클론 서버  | `/srv/excavator/gulsakgi-nara`, http://211.110.140.201:8001/ |

| 확인 항목           | 조치 |
|---------------------|------|
| 클론 URL (8001)     | 접속 주소 확인, 필요 시 `?v=값` 추가 |
| 반영 안 됨          | `gunicorn-gulsakgi-clone`, `nginx` 재시작 |
| 모바일에서 동일     | 시크릿 모드 / 강력 새로고침 / `?v=값` |
