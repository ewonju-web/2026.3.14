# 굴삭기나라 아키텍처 개요

필터/검색 강화 시 참고용 구조 요약입니다. 여기에 필요한 항목을 추가해 사용하시면 됩니다.

---

## 1. 프로젝트 구조

```
gulsakgi-nara/
├── config/                 # Django 설정
│   ├── settings.py
│   └── urls.py             # '' → equipment.urls, /chat/, /soil/, /admin/ 등
├── equipment/              # 메인 앱: 장비 매물, 구인구직, 부품, 업체
│   ├── models.py           # Equipment, JobPost, Part, PartsShop, Comment 등
│   ├── views.py            # 목록/상세/등록/수정 (검색·필터 로직 포함)
│   ├── filters.py          # django_filters (EquipmentFilter) — 현재 목록뷰와 미연동
│   ├── forms.py
│   ├── urls.py
│   └── ...
├── chat/                   # 1:1 채팅
├── soil/                   # 흙/자재 게시판
├── accounts/               # 결제·멤버십
├── users/                  # 프로필 등
└── templates/
    └── equipment/
        ├── equipment_list.html   # 메인 매물 목록 (검색/정렬 UI)
        ├── equipment_detail.html
        └── ...
```

---

## 2. 메인 매물 검색·필터 (실제 동작 중인 부분)

- **진입점**: `equipment/views.index` → URL `/` (name: `index`)
- **템플릿**: `templates/equipment/equipment_list.html`
- **쿼리 파라미터**:
  - `q`: 검색어
  - `category`: 기종 (excavator, forklift, dump, loader, attachment, etc)
  - `sort`: 정렬 (new | price_asc | price_desc)

### 2.1 현재 검색 로직 (views.index)

- 기본 쿼리: `Equipment.objects.visible()` (listing_status=NORMAL)
- **카테고리**: `category` 값이 유효하면 `equipment_type`으로 필터
- **검색어 `q`**:
  - 텍스트: `model_name`, `manufacturer`, `current_location` 에 대해 `icontains`
  - 숫자 처리:
    - 정수로 파싱 가능하면 `listing_price` (가격) 일치
    - 4자리 숫자(1980~2030)면 `year_manufactured` (연식) 일치
- **정렬**: 최신순 / 가격 오름·내림

### 2.2 Equipment 모델에서 필터 가능한 필드 (현재)

| 필드 | 타입 | 비고 |
|------|------|------|
| equipment_type | CharField | 기종 (excavator, forklift, dump, loader, attachment, etc) |
| model_name | CharField | 모델명 |
| manufacturer | CharField | 제조사 |
| year_manufactured | IntegerField, null | 제작년도 |
| month_manufactured | IntegerField, null | 제작월 |
| operating_hours | IntegerField | 가동시간(hr) |
| listing_price | DecimalField | 판매가격 |
| current_location | CharField | 현재 위치 |
| vehicle_number | CharField | 차량번호 |
| description | CharField | 상세 설명 |
| is_sold | BooleanField | 판매완료 여부 |
| listing_status | CharField | NORMAL / EXPIRED_HIDDEN |
| created_at | DateTimeField | 등록일 |

---

## 3. 필터 강화 시 수정 포인트 (골격)

아래는 “검색/필터 강화” 시 건드리면 되는 위치만 정리한 것입니다. 요구사항에 맞게 항목을 추가·수정해 사용하시면 됩니다.

### 3.1 백엔드

- **`equipment/views.py`의 `index`**
  - GET 파라미터 추가 (예: 연식 범위, 가격 범위, 가동시간, 제조사, 지역 등).
  - `equipment_list`에 적용할 `.filter()`, `.order_by()` 조건 추가.
  - 새 파라미터를 템플릿으로 넘기기 (예: `filter_year_min`, `filter_price_max` …).

- **`equipment/filters.py` (선택)**
  - 현재 `EquipmentFilter`는 목록뷰와 연결되어 있지 않음.
  - API나 공통 필터셋으로 쓸 계획이면: Equipment 모델 필드에 맞게 수정 (category → equipment_type, hours_used → operating_hours 등).
  - 웹 목록만 쓸 경우: views.index에서 직접 Q 객체로 처리해도 됨.

### 3.2 프론트(템플릿)

- **`templates/equipment/equipment_list.html`**
  - PC: `gn-pc-search-form` 등 기존 폼에 hidden/select/input 추가 (연식, 가격, 가동시간, 제조사, 지역 등).
  - 모바일: 필요 시 검색/필터 영역에 동일 파라미터 반영.
  - 링크(카테고리 등)에 기존 `q`, `sort`와 함께 새 파라미터 유지 (예: `&year_min=2020&price_max=5000`).

### 3.3 URL/파라미터 설계 (예시)

- 지금: `?q=검색어&category=excavator&sort=new`
- 강화 예:  
  `?q=...&category=...&sort=...&year_min=...&year_max=...&price_min=...&price_max=...&hours_max=...&manufacturer=...&region=...`
- 파라미터 이름과 의미를 이 문서에 적어두면 나중에 유지보수하기 좋습니다.

### 3.4 성능/인덱스

- 연식·가격·가동시간·기종 등으로 자주 필터링하면 `equipment/models.py`의 Equipment 메타에 `db_index=True` 또는 `Index` 추가 검토.

---

## 4. 그 외 검색/필터 관련

- **구인구직** (`equipment/views.job_list`): `q`, `type`, `region_sido`, `region_sigungu` 로 필터.
- **부품** (`equipment/views.part_list`): `category` 로만 필터.
- **billing** (노출/프리미엄): `billing/services/exposure_ordering.py` 등에서 검색 키워드/카테고리/지역 기반 노출 제어.

---

## 5. 체크리스트 (필터 강화 시 채우기)

- [ ] 추가할 필터 항목 (예: 연식 범위, 가격 범위, 가동시간, 제조사, 시/도 …)
- [ ] URL 파라미터 이름 정리
- [ ] views.index 수정 (파라미터 읽기 → queryset 필터)
- [ ] equipment_list.html 수정 (폼/링크에 파라미터 반영)
- [ ] (선택) EquipmentFilter / API 필드 정리
- [ ] (선택) DB 인덱스 추가

이 문서를 복사해 “필터 강화” 전용 체크리스트나 상세 설계로 확장해 쓰시면 됩니다.
