# 장비(Equipment) 관련 코드 참조

기존 장비 매물 관련 **모델·폼·뷰·유틸** 위치와 요약입니다.

---

## 1. 모델 (`equipment/models.py`)

### Equipment
- **작성자**: `author` (FK User, null/blank 가능)
- **기종**: `equipment_type` (excavator, forklift, dump, loader, attachment, etc)
- **모델/제조사**: `model_name`, `manufacturer`
- **세부**: `sub_type`, `weight_class`, `mast_type` (지게차)
- **연식**: `year_manufactured`, `month_manufactured` (null 가능)
- **가동시간**: `operating_hours`
- **가격/위치**: `listing_price`, `current_location`, `region_sido`, `region_sigungu`
- **차량번호**: `vehicle_number`
- **상태**: `is_sold`, `listing_status` (NORMAL / EXPIRED_HIDDEN), `last_bumped_at`, `legacy_listing_id`

### EquipmentImage
- `equipment` (FK), `image` (ImageField, upload_to='equipment_images/')

### DeletedListingLog (무료 회원 재등록 제한)
- `user`, `model_name`, `image_hash`, `deleted_at` — 삭제 시 저장, 30일 이내 동일 모델/사진 재등록 차단

### EquipmentQuerySet
- `visible()` → `listing_status=NORMAL` 만 필터

---

## 2. 폼 (`equipment/forms.py`)

### EquipmentForm
- **필드**: equipment_type, model_name, manufacturer, sub_type, weight_class, mast_type, year/month_manufactured, operating_hours, listing_price, current_location, region_sido, region_sigungu, vehicle_number, description
- **필수**: equipment_type, listing_price
- **clean**: year(1980~2100), month(1~12), vehicle_number 30자, description 50자

### EquipmentEditForm
- EquipmentForm 상속, 동일 필드 (작성자 전용 수정)

---

## 3. 뷰·URL (`equipment/views.py` · `equipment/urls.py`)

| URL | 뷰 | 설명 |
|-----|-----|------|
| `/` | `index` | 목록·검색·필터. NORMAL만. 정렬(최신/가격), 끌어올리기 반영, 유료 상단 노출, 로테이션/사이드바 |
| `/equipment/<pk>/` | `equipment_detail` | 상세. 댓글, 금융 예상, 비슷한 매물, 판매자 다른 매물 6개, bump 버튼(유료·주 1회) |
| `/equipment/create/` | `equipment_create` | 등록. 로그인+휴대폰 인증 필수. 무료 10건/월, 재등록 30일 제한, 사진 1장 이상 |
| `/equipment/<pk>/edit/` | `equipment_edit` | 수정. 본인만 |
| `/equipment/<pk>/delete/` | `equipment_delete` | 삭제. 본인만. 무료 회원 시 DeletedListingLog 기록 |
| `/equipment/<pk>/bump/` | `equipment_bump` | 끌어올리기. 유료 회원만, 주 1회. last_bumped_at 갱신 |

---

## 4. 인덱스(목록) 로직 요약 (`index`)

- 쿼리: `Equipment.objects.visible()` → category, q(모델명/제조사/위치/가격/년식), maker, model, year_min/max, region_sido/sigungu, sub_type, weight_class, mast_type
- 정렬: price_asc / price_desc / new(기본). new일 때 `Coalesce(last_bumped_at, created_at)` 내림차순
- 유료 회원 매물을 목록 **상단**에 배치
- 로테이션: `get_premium_equipment_rotation(18)` → 6건씩 슬라이드
- 사이드바: `get_premium_equipment_sidebar(6)` → 랜덤 6건

---

## 5. 등록 로직 요약 (`equipment_create`)

1. 로그인 체크 → 휴대폰 인증(`_require_phone_verified`) 미완료 시 `/account/verify-phone/?next=...` 리다이렉트
2. 무료 회원: `get_free_listing_count(user) >= 10` 이면 등록 불가 메시지
3. 사진 최소 1장 필수
4. 무료 회원: `DeletedListingLog` 에서 30일 이내 동일 `model_name` 또는 동일 `image_hash` 있으면 재등록 불가
5. 저장 시 `_build_location_text(current_location, region_sido, region_sigungu)` 로 current_location 보정
6. 첫 이미지 해시 계산 후 `seek(0)` 해서 이미지 저장 (포인터 초기화)

---

## 6. 삭제 로직 요약 (`equipment_delete`)

- 본인만 삭제 가능
- 무료 회원일 때: `_image_hash_from_equipment(equipment)` + model_name 으로 `DeletedListingLog` 생성

---

## 7. 끌어올리기 (`equipment_bump`)

- 본인 매물 + 유료 회원만
- `last_bumped_at` 이 7일 이내면 불가, 가능하면 `last_bumped_at = now` 저장

---

## 8. 유틸 (`equipment/premium_utils.py`)

- `get_premium_user_ids()` — 유료(기간 유효) user id 목록
- `is_user_premium(user)` — 유료 여부
- `get_free_listing_count(user)` — 당월 등록 건수 (삭제 포함)
- `FREE_LISTING_LIMIT = 10`
- `get_premium_equipment_rotation(limit=18)` — 로테이션용
- `get_premium_equipment_sidebar(limit=6)` — 우측 배너용

---

## 9. 뷰 내부 헬퍼 (`equipment/views.py`)

- `_image_hash_from_upload(uploaded_file)` — 업로드 파일 MD5 (재등록 감지)
- `_image_hash_from_equipment(equipment)` — 대표 사진 MD5 (삭제 시 로그)
- `_get_profile_phone_verified(user)` — 휴대폰 인증 여부
- `_require_phone_verified(request, next_url=None)` — 미인증 시 `/account/verify-phone/?next=...` 리다이렉트
- `_build_location_text(current_location, region_sido, region_sigungu)` — 위치 문자열 조합

---

## 10. 파일 위치 정리

| 내용 | 파일 |
|------|------|
| Equipment, EquipmentImage, DeletedListingLog, EquipmentQuerySet | `equipment/models.py` |
| EquipmentForm, EquipmentEditForm | `equipment/forms.py` |
| index, equipment_detail, equipment_create, equipment_edit, equipment_delete, equipment_bump | `equipment/views.py` |
| 유료/무료 한도·로테이션·사이드바 | `equipment/premium_utils.py` |
| 장비 URL 라우팅 | `equipment/urls.py` |

이 문서를 기준으로 장비 관련 수정·확장 시 참고하면 됩니다.
