# Billing(유료화) 개발 가이드

**목적:** Billing(유료화) 구현 시 개발자가 참고할 요약 문서.

- **실제 구현은 기존 코드를 그대로 참고**한다.
  - `billing/models.py`
  - `billing/admin.py`
  - `billing/services/exposure_ordering.py`
- 본 문서는 **개발할 때 보면 되는 요약 + 템플릿용 코드**만 제공한다.

**포함 범위:**  
1) 구현 코드 템플릿 정리(모델/어드민/노출 로직)  
2) SEARCH_TOP → SEARCH_MATCH 데이터 마이그레이션  
3) UniqueConstraint/인덱스 보강 판단 가이드  

---

## 공정 정렬(paid_at ASC)

- 프리미엄 노출 정렬은 **paid_at ASC** (먼저 결제한 사람 우선, 분쟁 방지).
- **권장 정렬 키:** `order_by('paid_at', 'id')`.
- ※ **정렬 전제:** `PremiumPlacement.paid_at`은 NULL이 아니어야 한다. 결제 성공 시 반드시 설정한다. NULL이면 정렬 시 공정성 논란이 발생할 수 있다.
- **모델 레벨(실무):** `PremiumPlacement.paid_at`은 **null=False**로 정의한다. 기존 레코드가 있으면 paid_at 백필 후 null=False 변경이 필요하다. (결제 성공 후에만 Placement 생성, paid_at은 Payment.paid_at 복사.) DB가 NULL 허용이면 언젠가 NULL이 들어간다. 결제 성공 후에만 Placement를 생성하도록 설계한다. 대기열 생성도 “결제 성공 직후”에만 만들고, `paid_at`은 `Payment.paid_at`을 그대로 복사한다.
- **Placement 생성 시점:** `Payment.status == SUCCESS`(또는 `Order.status == PAID`) 전에는 생성하지 않는다. 결제 전 PENDING 상태에서 placement를 미리 만들지 않는다.
- **Payment 보강:** Payment는 **status=SUCCESS일 때 paid_at이 반드시 채워지도록** 서비스 레이어에서 강제한다(예: 결제 콜백 처리에서 set). 엄격하게 하려면 DB CheckConstraint도 가능하나, 우선 서비스 레벨 강제가 현실적이다.
- **paid_at 값:** `Payment.paid_at`을 복사한다. 서버 `now()` 사용은 금지 권장(공정성·재현성).
- **타임존/시각(공정성·재현성):** `paid_at`은 timezone-aware **UTC**(Django `USE_TZ=True`)로 저장한다. 표시(UI)는 KST로 변환하되, 정렬/비교는 UTC 기준으로 한다.

---

## 대기열 기간 카운트 규칙(슬롯 배정 시점부터 시작)

**프리미엄 기간은 슬롯 배정 시점(starts_at)부터 카운트한다. 대기열 동안은 기간 차감이 없다.**

대기열(`PremiumPlacement.slot_no IS NULL`) 상태에서는 `starts_at`/`expires_at`을 확정하지 않으며, **슬롯 배정 시점에** `starts_at=now`, `expires_at=now+duration_days` 로 설정한다. 이 한 줄을 운영 정책으로 명시해 두지 않으면 대기열이 길어졌을 때 CS/분쟁이 발생하기 쉽다.

- **DB 스키마 권장:** 대기열을 운영할 경우 `PremiumPlacement.starts_at`/`expires_at`은 **null=True** 로 두고, 승격(ACTIVE) 시점에만 값 세팅한다. null=False이면 대기열 생성 시 값을 채울 수 없어 정책과 충돌한다.

**슬롯 승격 로직(경합 방지):** 슬롯 승격은 `transaction.atomic()` + `select_for_update()` 로 처리한다. 동시 요청 시 동일 대기열 항목이 중복 승격되는 것을 방지한다. 이 처리가 없으면 실운영에서 간헐적 중복 배정 버그가 발생할 수 있다. 슬롯 승격 중 유니크 충돌이 발생하면(IntegrityError) 짧게 재시도하거나, 다음 대기열 항목을 다시 조회한다. UniqueConstraint + select_for_update를 써도 배포 직후·트래픽 급증 시 아주 드물게 충돌이 난다.

---

## 1) 구현 코드 템플릿 정리

### 1.1 models.py 요약

**경로:** `billing/models.py`  
(장비 모델은 `equipment/models.py` 참고: `Equipment.listing_status` = `NORMAL | EXPIRED_HIDDEN`)

| 모델 | 역할 | 핵심 필드(요약) |
|------|------|-----------------|
| **Product** | 요금제 마스터 | `code`, `name`, `product_type`, `slot_type(옵션)`, `duration_days`, `price`, `is_recurring`, `is_active` |
| **Order** | 주문(결제 단위) | `user`, `order_number`, `status(PENDING/PAID/...)`, `total_amount`, `admin_memo`, `refund_amount`, `refunded_at` |
| **OrderItem** | 주문 항목(상품 1개 단위) | `order`, `product`, `quantity`, `unit_price`, `target_content_type/object_id`, `slot_type`, `starts_at`, `expires_at`, `metadata(JSON)` |
| **Payment** | PG 결제 기록 | `order`, `pg_provider`, `pg_tid`, `amount`, `status`, `requested_at`, `paid_at`, `raw_response(JSON)`, `admin_memo`, `refund_amount`, `refunded_at` |
| **PremiumPlacement** | 프리미엄 노출 제어(슬롯/대기열) | `status(WAITING/ACTIVE/EXPIRED/REFUNDED)`, `equipment`, `slot_type`, `slot_no(1~5 or NULL)`, `waitlist_rank(표시용)`, `paid_at(null=False)`, `category`, `region_key`, `match_keywords({"raw","norm"})`, `starts_at`/`expires_at`(null=대기열), `admin_memo`, `refunded_at`/`refund_amount`, `period_adjusted_at` |
| **EquipmentUpgrade** | 매물 업그레이드(강조/사진/재노출) | `equipment`, `max_images`, `is_highlight`, `bump_at`, `expires_at`, `order_item` |
| **DealerMembership** | 딜러 PRO 멤버십(구독) | `user(1:1)`, `period_start`, `period_end`, `is_auto_renew(2차)`, `order_item` |
| **RevenueDaily** | 매출 집계(일 단위) | `(date, product_code) unique`, `order_count`, `amount_sum` |
| **ConversionEvent** | 전환 로그(퍼널) | `event_type`, `user`, `session_key`, `content_type/object_id`, `metadata(JSON)`, `created_at` |

**SlotType 주의사항**

- `SEARCH_TOP`은 사용하지 않는다.
- `SEARCH_MATCH`만 사용한다.

**대기열·활성 구분 — status 필드(필수)**

- `PremiumPlacement.status`: **WAITING(대기) | ACTIVE(활성) | EXPIRED(만료) | REFUNDED(환불)**.
- 대기열 = `status=WAITING`, 슬롯 보유·노출 = `status=ACTIVE`. 노출 로직에서는 **status=ACTIVE**만 조회하고, 필요 시 `expires_at__gte=now`로 유효 기간 필터.
- **starts_at/expires_at**은 **null=True**. 대기열(WAITING)일 때는 비워 두고, **ACTIVE 전환 시점에만** `starts_at=now`, `expires_at=now+duration_days` 세팅. 이렇게 해야 “대기열 동안 기간 차감 없음” 정책과 DB가 일치한다.

**match_keywords 형식(V2.1)**

- `match_keywords`는 **dict** 권장: `{"raw": [...], "norm": [...]}`. 노출 로직에서는 **norm** 기준으로 검색어와 매칭한다. 레거시 리스트 형태도 호환 처리 가능.

**딜러 vs PRO 구분(혼선 방지)**

- **딜러 표시(매매상 배지):** `Profile.user_type == 'DEALER'` (작성자 프로필 기준, 신분).
- **PRO 혜택/노출 가중치:** `DealerMembership.is_active == True` (유료 구독 상태).
- admin/뷰에서 두 개념을 섞지 않고 위 룰대로 적용한다.

---

### 1.2 admin.py 요약

**경로:** `billing/admin.py`

| Admin | 핵심 설정(요약) |
|-------|-----------------|
| **ProductAdmin** | `list_display`: code, name, product_type, slot_type, price, is_active / list_filter / search_fields |
| **OrderAdmin** | list_display에 refund_amount, refunded_at 포함 / OrderItemInline, PaymentInline |
| **PaymentAdmin** | list_display에 pg_tid, amount, status, admin_memo, refund_* |
| **PremiumPlacementAdmin** | list_display: slot_no, waitlist_rank, paid_at, category, region_key, refunded_at, admin_memo / list_editable: is_active, slot_no, admin_memo |
| **EquipmentUpgradeAdmin** | equipment, max_images, is_highlight, bump_at, expires_at |
| **DealerMembershipAdmin** | user, period_start/end, is_auto_renew, is_active_display |
| **RevenueDailyAdmin** | date, product_code, order_count, amount_sum |
| **ConversionEventAdmin** | event_type, user, session_key, content_type, object_id, created_at / readonly / date_hierarchy 권장 |

---

### 1.3 exposure_ordering.py 요약

**경로:** `billing/services/exposure_ordering.py`

| 함수 | 설명 |
|------|------|
| `get_category_top_equipment_ids(category, slot_count=5)` | **카테고리 TOP 슬롯 1~5 + 대기열** 구성. 공정 정렬: paid_at ASC |
| `get_region_top_equipment_ids(region_key, limit=5)` | 지역 TOP 노출. 공정 정렬: paid_at ASC |
| `get_search_match_equipment_ids(category, region_key, search_keywords, limit=5)` | **SEARCH_MATCH만 허용**. 카테고리/지역 필수 + 키워드 매칭(선택) |
| `get_bump_equipment_ids(limit=3, bump_hours=24)` | 업그레이드 bump 후보 최대 1~3개 |
| `merge_list_with_bump(main_ids, bump_ids, max_bump=3)` | 목록에 bump를 **최대 1~3개만** 섞어 반환 |

#### 뷰에서 사용 예시

```python
from billing.services.exposure_ordering import (
    get_category_top_equipment_ids,
    get_bump_equipment_ids,
    merge_list_with_bump,
)
from equipment.models import Equipment

filter_category = request.GET.get("category", "")  # 또는 현재 탭
premium_ids = get_category_top_equipment_ids(filter_category) if filter_category else []

bump_ids = get_bump_equipment_ids(limit=3)

# 일반 매물 (NORMAL만, 최신순). Equipment.objects.visible() 사용 권장.
normal_ids = list(
    Equipment.objects.visible()
    .exclude(id__in=premium_ids)
    .order_by("-created_at")
    .values_list("id", flat=True)
)

ordered_ids = merge_list_with_bump(premium_ids + normal_ids, bump_ids, max_bump=3)

# ordered_ids 순서를 보장해서 Equipment 조회 (이 코드가 없으면 Django는 id 기준으로 정렬해 버림)
from django.db.models import Case, When, Value, IntegerField

preserved_order = Case(
    *[When(id=pk, then=Value(pos)) for pos, pk in enumerate(ordered_ids)],
    default=Value(len(ordered_ids)),
    output_field=IntegerField(),
)
equipment_list = (
    Equipment.objects.none()
    if not ordered_ids
    else Equipment.objects.filter(id__in=ordered_ids).order_by(preserved_order)
)
```

### REGION_TOP 정책

- REGION_TOP은 CATEGORY_TOP과 달리 **슬롯 고정(1~5) 운영을 하지 않는다.**
- 상단 N개(limit=5 등)만 `paid_at ASC` 기준으로 노출한다.
- REGION_TOP에는 `slot_no` 유니크 제약을 적용하지 않는다.

→ 이 정책을 명시해 두지 않으면 개발자가 REGION_TOP에도 슬롯을 만들 가능성이 있다.

### region_key 생성 규칙(Equipment 연동)

- **PremiumPlacement.region_key**는 **무조건** `normalize_region_key(equipment.current_location)` 으로 채운다.
- "서울 강남구 역삼동" / "서울시 강남구" 등 표기가 들쭉날쭉하면 REGION_TOP·SEARCH_MATCH 매칭이 깨지므로, Placement 생성·마이그레이션 시 반드시 정규화 함수 사용.
- **경로:** `billing/services/region.py` → `normalize_region_key(s)`  
  (공백 정리, 서울시/서울특별시 → 서울 등 간단 매핑, 앞 50자 반환.)

### SEARCH_MATCH 키워드 매칭 방식

- 1차 구현에서는 DB에서 후보를 조회한 뒤, **파이썬 레벨에서** normalize 후 포함 여부를 필터링한다.
- normalize 예: 소문자 변환, 공백 제거, ton/톤 → t 통일.
- 성능 이슈 발생 시 PostgreSQL **GIN 인덱스** 기반 JSON 검색으로 고도화한다.

→ 문서에 "키워드 매칭"만 있으면 구현 전략이 빠져 있으므로 위와 같이 명시한다.

---

## 2) SEARCH_TOP → SEARCH_MATCH 데이터 마이그레이션

**목적:** 과거 DB에 `slot_type='SEARCH_TOP'` 값이 남아 있을 수 있으므로 1회 정리한다.  
모델 코드에서 SEARCH_TOP을 제거했더라도, DB 레코드 값은 남아 있을 수 있음.

**실행 시점:** Billing 모델에서 SEARCH_TOP enum을 제거한 상태면, DB에 SEARCH_TOP 문자열이 남아 있을 때 관리자/조회에서 에러가 날 수 있다. 따라서 **배포 직전 또는 직후**에 반드시 1회 실행한다.

### 2.1 스크립트

⚠️ **shell 리다이렉트 방식은 테스트 서버에서만 사용 권장.**  
운영/본배포에서는 Data migration 또는 Management command로 수행한다.

**경로:** `scripts/migrate_search_top_to_search_match.py`

- `slot_type='SEARCH_TOP'` → `'SEARCH_MATCH'` UPDATE는 **transaction.atomic()** 으로 감싸서 롤백 가능.
- `category`/`region_key`가 **비어 있는 행만** 대상으로 채움(전체 스캔 방지).
- `region_key`는 **normalize_region_key(equipment.current_location)** 사용(매칭 깨짐 방지).
- category 기본값 `excavator` 사용. (현재 단일 카테고리 전제. 멀티 카테고리 도입 시 equipment 기반 매핑 필요.)
- 채우기는 **bulk_update** 로 일괄 처리(batch_size=1000).
- 실행 전/후 SEARCH_TOP·SEARCH_MATCH 건수 및 empty category/region_key 건수 출력.

### 2.2 실행

```bash
cd /path/to/gulsakgi-nara
python manage.py shell < scripts/migrate_search_top_to_search_match.py
```

운영/본배포에서는 Data migration 또는 Management command 사용 권장. 테스트 서버에서만 위 shell 리다이렉트 사용.

---

## 3) UniqueConstraint(조건부) / 인덱스 보강

### 3.1 UniqueConstraint(조건부) — 유지 권장

- **대상:** PremiumPlacement
- 동일 카테고리에서 `(slot_type, category, slot_no)` 중복 배정되면 슬롯(1~5) 운영이 꼬임
- 대기열은 `slot_no=NULL` 다건 허용이 필요하므로 **조건부 유니크**가 맞음
- **slot_no가 있으면 1~5만 허용**되도록 CheckConstraint 추가. UniqueConstraint는 중복만 막고 범위(예: 999)는 막지 못한다.

예시:

```python
from django.db.models import Q

# slot_no 범위 1~5(대기열 NULL 허용)
models.CheckConstraint(
    check=Q(slot_no__isnull=True) | (Q(slot_no__gte=1) & Q(slot_no__lte=5)),
    name="billing_pp_slot_no_range_1_5",
)
models.UniqueConstraint(
    fields=["slot_type", "category", "slot_no"],
    condition=Q(slot_type=SlotType.CATEGORY_TOP, slot_no__isnull=False),
    name="billing_placement_category_slot_unique",
)
```

### 3.2 인덱스 — 초기에는 현재 정의만으로 충분

**원칙**

- 초기: 현재 `models.py`에 정의된 인덱스로 운영 가능
- 트래픽/데이터 증가 후, 느려질 때만 보강

**추가 고려 인덱스**

| 상황 | 인덱스 | 이유 |
|------|--------|------|
| 카테고리 대기열 조회가 느려짐 | `(slot_type, category, paid_at)` | 대기열 정렬 paid_at ASC 최적화 |
| 슬롯 조회가 잦은 경우 | `(slot_type, category, slot_no, expires_at)` | 활성 슬롯 조회 최적화 |
| 전환 로그 조회/집계가 많음 | `(event_type, created_at)` | 퍼널 집계/대시보드 최적화(이미 있으면 추가 불필요) |

추가 예시:

```python
# 대기열 paid_at ASC 정렬 최적화
models.Index(
    fields=["slot_type", "category", "paid_at"],
    name="billing_pp_waitlist_paid",
),
# 활성 슬롯 조회 최적화
models.Index(
    fields=["slot_type", "category", "slot_no", "expires_at"],
    name="billing_pp_slot_exp",
),
```

---

## 4) 체크리스트

- [ ] `billing/models.py` / `billing/admin.py` / `billing/services/exposure_ordering.py` 구현 반영
- [ ] `equipment/models.py`에 `Equipment.listing_status` 추가 및 마이그레이션
- [ ] (필요 시) SEARCH_TOP → SEARCH_MATCH 스크립트 1회 실행
- [ ] 조건부 UniqueConstraint 유지
- [ ] 인덱스는 초기엔 현재 정의 유지, 성능 이슈 시 `(slot_type, category, paid_at)` 등 보강
- [ ] **대기열 기간 정책(슬롯 배정 시점부터 카운트)** 적용 여부 확인
- [ ] PremiumPlacement `starts_at`/`expires_at` null=True 반영(대기열 시 미확정)
- [ ] Payment 콜백에서 status=SUCCESS 시 `paid_at` 서비스 레이어 강제 설정
- [ ] CATEGORY_TOP `slot_no` 1~5 범위 CheckConstraint 적용 여부 확인
- [ ] **PremiumPlacement.paid_at null=False** 유지, Payment SUCCESS 이후에만 Placement 생성
- [ ] **status + starts_at/expires_at null**: 대기열은 WAITING·기간 미확정, ACTIVE 전환 시에만 starts/expires 세팅
- [ ] **실무 보강:** OrderItem.target_object_id / ConversionEvent.object_id → PositiveBigIntegerField 권장(장비 PK 확장). Payment.pg_tid → null=True, blank=True 권장.
- [ ] **region_key:** Placement 생성/마이그레이션 시 `normalize_region_key(equipment.current_location)` 사용. Equipment 연동 시 REGION_TOP/SEARCH_MATCH 안정 동작.
