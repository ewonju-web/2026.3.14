# NHN 호스팅 direct-nara.co.kr 백업 및 이관 가이드

NHN 호스팅에 있는 **기존 사이트 direct-nara.co.kr** 의 DB와 사이트를 파악하고, 백업을 받아 현재 서버(굴삭기나라 리뉴얼)로 옮기기 위한 실무 절차입니다.

---

## 0. 사전 파악 (필수)

이관 전에 **기존 사이트가 어떤 기술로 만들어졌는지** 먼저 확인해야 합니다.

| 확인 항목 | 방법 |
|-----------|------|
| **사이트 기술** | direct-nara.co.kr 접속 → 소스 보기 / URL 패턴 (`.php`, `.html`, Django 식 경로 등) |
| **DB 종류** | NHN 호스팅 콘솔에서 DB 정보 확인 (MySQL / MariaDB / PostgreSQL 등) |
| **파일 위치** | NHN 호스팅에서 웹 루트 경로, 업로드 파일(media) 경로 확인 |
| **접속 방식** | FTP/SFTP, SSH, NHN 클라우드 콘솔 등 |

**Cursor에서 NHN 서버 SSH로 연결해 파악·다운로드**하려면 → **`docs/CURSOR_NHN_SERVER_CONNECT.md`**

- NHN 클라우드/호스팅 **콘솔**에 로그인해 **서버/DB/스토리지** 메뉴에서 위 항목을 확인하세요.
- 기존이 **PHP+MySQL** 이면 덤프/복원 방식이 다르고, **Django+SQLite** 등이면 파일 복사 위주가 됩니다.

---

## 1. NHN 호스팅에서 백업 받기

### 1.1 DB 백업

**MySQL/MariaDB 인 경우 (가장 흔함)**

- NHN 콘솔에서 **DB 인스턴스** 선택 후 **백업** 기능이 있으면 그대로 사용.
- 또는 **SSH/FTP**로 서버 접속이 되면:

```bash
# MySQL 덤프 (원격 서버에서 실행)
mysqldump -u [DB사용자] -p [DB이름] > direct_nara_backup_$(date +%Y%m%d).sql
```

- **phpMyAdmin**이 있다면: 로그인 → DB 선택 → **내보내기(Export)** → SQL 파일 저장.

**※ direct-nara 실서버 백업 결과 (2026-03-08 기준)**  
- DB: MySQL, 호스트 `localhost`, DB/사용자 `ewonju12345`  
- 백업 파일: `/www/ewonju12345/db_backup_20260308.sql` (약 48MB)  
- 복원 예시: `mysql -u ewonju12345 -p -h localhost ewonju12345 < db_backup_20260308.sql`  
- 다른 서버/PC로 옮길 때: FTP/SFTP로 `db_backup_20260308.sql` 복사 후 위 명령으로 복원  
- 보안: `LeeDbtool_1/config.inc.php`에 DB 비밀번호가 평문으로 있음 → 권한 제한 또는 환경변수/배포 시 제거 권장  

**PC로 덤프 받기 (임시 다운로드 URL)**  
- 에이전트/스크립트는 서버 안에서만 동작하므로, 사용자 PC에 직접 저장할 수 없음.  
- 서버에 `tmp_dl/dl.php` 처럼 “한 번만 열면 덤프가 내려가게” 해 두고, **PC 브라우저**에서 해당 URL을 열어 받는 방식을 쓸 수 있음.  
- 예: `http://serverhosting21-57.godo.co.kr/tmp_dl/dl.php` (사이트가 다른 도메인이면 호스트만 해당 도메인으로 변경).  
- **다운로드가 끝나면** `tmp_dl` 폴더와 그 안의 `dl.php`를 서버에서 삭제하는 것이 좋음 (아래 “다운로드 후 삭제” 참고).

**다운로드 후 삭제 (tmp_dl 정리)**  
- Cursor로 NHN 서버에 SSH 연결된 터미널에서:
```bash
# 웹 루트 기준으로 tmp_dl 경로일 때 예시 (실제 경로에 맞게 수정)
rm -rf /www/ewonju12345/tmp_dl
```
- 또는 Cursor 탐색기에서 `tmp_dl` 폴더 우클릭 → 삭제.  
- 삭제 후 브라우저에서 해당 URL 다시 열면 404 등으로 더 이상 덤프가 내려가지 않아야 함.

**PostgreSQL 인 경우**

```bash
pg_dump -U [사용자] [DB이름] -F c -f direct_nara_backup_$(date +%Y%m%d).dump
```

**SQLite 인 경우**

- `db.sqlite3` 등 DB 파일이 있는 경로를 찾아서 해당 파일 통째로 복사.

### 1.2 사이트 파일 백업

- **웹 루트**: HTML/PHP/Django 등 소스 코드가 있는 디렉터리 전체.
- **업로드 파일**: 이미지/첨부 등이 저장된 디렉터리(예: `uploads/`, `media/`, `images/`).

**FTP/SFTP로 받는 경우**

- FileZilla 등으로 NHN 호스팅 접속 후:
  - 웹 루트 폴더 전체 다운로드
  - DB 덤프 파일 또는 SQLite 파일 다운로드
  - 업로드/미디어 폴더 다운로드

**NHN에서 제공하는 스냅샷/백업**

- NHN 호스팅에서 **서버 스냅샷** 또는 **백업 다운로드** 기능이 있으면, 그걸로 전체 백업 후 필요한 부분만 추출해도 됩니다.

---

## 2. 현재 서버로 옮기기

### 2.1 백업 파일을 현재 서버로 복사

```bash
# 예: SCP로 복사 (로컬 PC에서 현재 서버로)
scp direct_nara_backup_20260307.sql user@211.110.140.201:/tmp/
scp -r direct_nara_site_files user@211.110.140.201:/tmp/
```

- 또는 FTP/SFTP로 **211.110.140.201** 서버에 업로드.

### 2.2 기존 DB 구조 파악 (이관 설계용)

- MySQL 덤프를 받았다면:

```bash
# 덤프 파일에서 테이블 목록만 빠르게 보기
grep "CREATE TABLE" direct_nara_backup_20260307.sql
```

- **테이블 이름·컬럼**을 보면 “회원”, “매물”, “이미지”가 어떤 식으로 되어 있는지 알 수 있습니다.
- 이 구조를 기준으로 `docs/MIGRATION_DIRECT_NARA.md` 의 **legacy_id 매핑·이관 순서**를 적용합니다.

### 2.3 리뉴얼 사이트(현재)와 기술 스택이 다를 때

- **기존**: PHP + MySQL  
- **현재(리뉴얼)**: Django + SQLite (또는 PostgreSQL)

이 경우 **DB를 그대로 붙여넣기보다는**:

1. 기존 DB 덤프를 **현재 서버에 임시 MySQL 등으로 복원**하고,
2. **이관 스크립트**(Python/Django management command)로 기존 테이블을 읽어서  
   현재 Django 모델(Equipment, User, Profile 등)에 **legacy_*_id** 를 넣어가며 이관하는 방식을 권장합니다.
3. 이미지/미디어는 **파일 경로 매핑**해서 `MEDIA_ROOT` 쪽으로 복사하면 됩니다.

---

## 3. 요약 체크리스트

| 단계 | 작업 |
|------|------|
| 1 | NHN 콘솔/접속으로 direct-nara.co.kr **사이트 기술·DB 종류·경로** 파악 |
| 2 | **DB 백업**: mysqldump / pg_dump / SQLite 파일 복사 |
| 3 | **사이트 파일 백업**: 웹 루트 + 업로드(media) 폴더 |
| 4 | 백업 파일을 **현재 서버**(211.110.140.201 등)로 복사 |
| 5 | 덤프/테이블 구조 확인 후 `MIGRATION_DIRECT_NARA.md` 참고해 **이관 스크립트** 설계·실행 |
| 6 | 도메인 전환 시 `ALLOWED_HOSTS`에 `direct-nara.co.kr` 추가, SSL/리다이렉트 설정 |

---

## 4. 참고 문서

- **DB 이관 설계(매핑·순서·재실행)**  
  → `docs/MIGRATION_DIRECT_NARA.md`  
- **배포·재시작**  
  → `docs/DEPLOY_CHECKLIST.md`  
- **도메인·SSL**  
  → `docs/NEXT_STEPS.md` 4번

---

## 5. 다음 단계: NHN 서버 배포 및 도메인 연결

백업·이관이 끝난 뒤 **NHN 서버에서 정상 사이트로 도메인 연결**하려면:

→ **`docs/NHN_DEPLOY_DOMAIN_GUIDE.md`**  
(시험 후 NHN 서버 배포, direct-nara.co.kr DNS·SSL·동작 확인까지 순서 정리)

---

## 6. NHN 호스팅 관련 참고

- NHN 클라우드/호스팅 **고객센터** 또는 **매뉴얼**에서  
  “백업”, “DB 내보내기”, “FTP/SSH 접속” 항목을 확인하면, 위 1~2단계를 더 구체적으로 채울 수 있습니다.
- **DB 비밀번호·호스트**는 NHN 콘솔의 DB 상세 정보에서 확인하세요.  
  보안을 위해 이 문서에는 실제 접속 정보를 적지 않습니다.

---

이 가이드대로 진행하면 direct-nara.co.kr의 DB와 사이트를 백업하고, 현재 서버로 옮겨와서 리뉴얼 DB와 연동할 수 있습니다.  
이관 스크립트는 `MIGRATION_DIRECT_NARA.md`의 설계를 따르면 됩니다.
