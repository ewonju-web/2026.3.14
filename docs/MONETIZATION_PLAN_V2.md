# 굴삭기나라 유료화 기획서 V2 (개선안 반영)

**기반:** MONETIZATION_PLAN.md  
**개선 요구 반영:** 공정 노출, 슬롯/대기열, SEARCH_TOP 제한, bump 제한, 만료 숨김, 환불 정책, PRO 단계별, 전환 로그

---

## 목차
1. [개선 요약](#1-개선-요약)
2. [수정된 DB 스키마(ERD/테이블)](#2-수정된-db-스키마erd테이블)
3. [핵심 쿼리/정렬 알고리즘](#3-핵심-쿼리정렬-알고리즘)
4. [관리자 기능 변경점](#4-관리자-기능-변경점)
5. [출시 순서(마일스톤)](#5-출시-순서마일스톤)

---

## 1. 개선 요약

| 개선 항목 | 기존 | 변경 후 |
|-----------|------|---------|
| 프리미엄 정렬 | expires_at DESC (곧 만료 우선) | **paid_at ASC** (먼저 결제한 사람 우선, 공정) |
| 카테고리 TOP | 단순 노출 순서 | **고정 슬롯 5칸(slot_no 1~5) + 대기열(waitlist)** |
| SEARCH_TOP | 무조건 검색 상단 노출 | **금지** → metadata 조건 매칭형(카테고리/지역/키워드) 또는 최소 카테고리+지역 제한 |
| 업그레이드 bump | 전체 목록 정렬에 반영 | **목록에 1~3개만 섞기** 또는 **별도 섹션** |
| 무료 만료 | 삭제 | **EXPIRED_HIDDEN 상태** + 1클릭 연장/업그레이드 전환 UX |
| 환불/취소 | 미정의 | **Order/Payment/Placement**에 부분환불, 기간조정, **admin_memo** 반영 |
| PRO 결제 | 정기결제 전제 | **1차 수동 연장 결제** → **2차 정기결제** 단계별 |
| 전환 분석 | 없음 | **이벤트 로그 테이블** 추가 |

---

## 2. 수정된 DB 스키마(ERD/테이블)

### 2.1 ER 개요 (변경 강조)

```
[User] 1----* [Equipment]
  |              |
  |              +-- status: NORMAL | EXPIRED_HIDDEN  (만료 시 숨김, 삭제 X)
  |              *----[PremiumPlacement]
  |                    +-- slot_no (1~5) NULL=대기열
  |                    +-- waitlist_rank (대기열 순서)
  |                    +-- admin_memo, refund_*
  |              *----[EquipmentUpgrade]
  |
  *----[DealerMembership]   (1차 수동 연장만, 2차에 is_auto_renew)
  *----[Order]   +-- admin_memo, refund_amount, status 확장
  *----[Payment] +-- admin_memo, refund_*
  *----[ConversionEvent]   (전환 로그)
```

### 2.2 Equipment 상태 (기존 모델 확장)

무료 30일 만료 시 **삭제하지 않고** 상태만 변경.

| 필드 | 타입 | 설명 |
|------|------|------|
| listing_status | VARCHAR(20) | `NORMAL` \| `EXPIRED_HIDDEN` (만료 후 숨김, 1클릭 연장/업그레이드 유도) |

- 목록/검색: `listing_status = 'NORMAL'` 만 노출.
- 상세 직접 URL은 접근 가능하게 하여 "연장하기" / "업그레이드하기" CTA 노출.

### 2.3 PremiumPlacement (수정)

| 필드 | 타입 | 설명 |
|------|------|------|
| id | PK | |
| equipment_id | FK(Equipment) | |
| slot_type | VARCHAR(20) | **CATEGORY_TOP** \| **REGION_TOP** \| **SEARCH_MATCH** (SEARCH_TOP 폐지) |
| **slot_no** | SMALLINT NULL | **1~5 고정 슬롯**. NULL이면 대기열. |
| **waitlist_rank** | INT NULL | 대기열일 때 순서 (작을수록 우선). paid_at ASC 기준. |
| category | VARCHAR(50) NULL | 카테고리 (excavator 등) |
| region_key | VARCHAR(50) NULL | 지역 키 |
| **match_keywords** | JSONB NULL | SEARCH_MATCH일 때만. 검색어 매칭 조건 (예: ["두산","25톤"]) |
| order_item_id | FK(OrderItem) | |
| starts_at | TIMESTAMP | |
| expires_at | TIMESTAMP | |
| **paid_at** | TIMESTAMP | 결제 시각 (공정 정렬용) |
| auto_renewable | BOOLEAN | |
| is_active | BOOLEAN | |
| **admin_memo** | TEXT NULL | 운영 메모 |
| **refunded_at** | TIMESTAMP NULL | 환불 처리 시각 |
| **refund_amount** | DECIMAL NULL | 환불 금액 (부분 환불) |
| **period_adjusted_at** | TIMESTAMP NULL | 기간 수동 조정 시각 |
| created_at | TIMESTAMP | |

**제약**
- `slot_type = 'CATEGORY_TOP'` 이고 `category` 가 있으면: **(category, slot_no)** 유니크. slot_no 1~5만 허용.
- **REGION_TOP**은 슬롯 고정 운영 안 함(상단 N개만 노출, 대기열 없음). get_region_top_equipment_ids(..., limit=5) 형태.
- SEARCH_TOP 제거 → **SEARCH_MATCH**: 카테고리+지역(필수) + 선택적으로 키워드 metadata. 검색 시 조건 일치할 때만 상단 노출.

**대기열 기간 정책(필수):** 대기열(`slot_no IS NULL`) 상태에서는 starts_at/expires_at을 확정하지 않으며, **슬롯 배정 시점에** starts_at=now, expires_at=now+duration_days 로 설정한다. 즉, **프리미엄 기간은 슬롯 배정 시점부터 카운트하며, 대기열 동안은 기간 차감 없음.**

### 2.4 Order / Payment (환불·메모 확장)

**Order**

| 추가 필드 | 타입 | 설명 |
|-----------|------|------|
| admin_memo | TEXT NULL | 운영 메모 |
| refund_amount | DECIMAL(10,2) NULL | 총 환불 금액 |
| refunded_at | TIMESTAMP NULL | 환불 처리 시각 |

**Payment**

| 추가 필드 | 타입 | 설명 |
|-----------|------|------|
| admin_memo | TEXT NULL | 운영 메모 |
| refund_amount | DECIMAL(10,2) NULL | 이 결제에 대한 환불 금액 |
| refunded_at | TIMESTAMP NULL | |

### 2.5 ConversionEvent (전환율 분석용 이벤트 로그)

| 필드 | 타입 | 설명 |
|------|------|------|
| id | PK | |
| event_type | VARCHAR(32) | 예: `listing_created`, `premium_click`, `checkout_start`, `payment_success`, `payment_fail`, `upgrade_click`, `pro_join_click`, `expired_extension_click` |
| user_id | FK(User) NULL | 로그인 사용자 |
| session_key | VARCHAR(64) NULL | 비로그인 세션 |
| content_type | FK(ContentType) NULL | 대상 (Equipment 등) |
| object_id | BIGINT NULL | |
| **metadata** | JSONB | 예: `{"slot_type":"CATEGORY_TOP","product_code":"PREMIUM_7D"}` |
| created_at | TIMESTAMP | |

- 인덱스: (event_type, created_at), (user_id, created_at)
- 목적: 퍼널 분석(노출→클릭→결제 시도→성공/실패), 전환율 계산

---

## 3. 핵심 쿼리/정렬 알고리즘

### 3.1 프리미엄 상단: paid_at ASC (공정)

**권장 정렬 키(분쟁 방지):** `order_by('paid_at', 'id')`

**의사코드**

```
프리미엄 노출 대상 선정 (카테고리 TOP, 슬롯 5칸):
  active_placements = PremiumPlacement
    .filter(slot_type='CATEGORY_TOP', category=current_category, is_active=True, expires_at >= now)
    .exclude(refunded_at__isnull=False)
    .order_by('slot_no')   # 1,2,3,4,5 순

  # 슬롯이 비었으면 대기열에서 채움 (paid_at ASC, id ASC = 먼저 결제한 사람, 분쟁 방지)
  filled_slots = {1..5} 에 대해
    slot_no 로 이미 있는 건 그대로
    없으면 waitlist 에서 order_by('paid_at', 'id') 1건 선택 → 해당 placement에 slot_no 부여(또는 가상으로 순서만 사용)

  노출 ID 목록 = filled_slots 순서대로 equipment_id 나열 (slot_no 1 → 2 → … → 5)
```

**Django ORM 예시 (카테고리 TOP 5칸)**

```python
from django.utils import timezone
from billing.models import PremiumPlacement, SlotType

def get_category_top_equipment_ids(category: str) -> list[int]:
    now = timezone.now()
    # 슬롯 보유 중인 것 (1~5)
    qs = PremiumPlacement.objects.filter(
        slot_type=SlotType.CATEGORY_TOP,
        category=category,
        is_active=True,
        expires_at__gte=now,
        refunded_at__isnull=True,
        slot_no__isnull=False,
    ).order_by('slot_no')
    slot_ids = list(qs.values_list('equipment_id', flat=True))

    # 5칸 미만이면 대기열에서 paid_at ASC로 채움
    need = 5 - len(slot_ids)
    if need > 0:
        waitlist = PremiumPlacement.objects.filter(
            slot_type=SlotType.CATEGORY_TOP,
            category=category,
            is_active=True,
            expires_at__gte=now,
            refunded_at__isnull=True,
            slot_no__isnull=True,
        ).order_by('paid_at', 'id').values_list('equipment_id', flat=True)[:need]
        slot_ids.extend(waitlist)
    return slot_ids[:5]
```

### 3.2 SEARCH_MATCH (검색 시 조건 매칭)

**규칙:** SEARCH_TOP(무조건 상단) 금지. **SEARCH_MATCH**만 사용.

**키워드 매칭:** 1차는 후보를 DB에서 가져온 뒤 파이썬에서 normalize 후 포함 여부를 필터링한다. 성능 이슈 발생 시 GIN 인덱스 기반으로 고도화.

- Placement의 **category** / **region_key** / **match_keywords**(선택) 가 **현재 검색 조건과 일치할 때만** 검색 결과 상단에 노출.
- 정렬: 동일하게 **paid_at ASC** (같은 조건 내에서 먼저 결제한 사람 우선).

**의사코드**

```
검색 조건: (category=c, region=r, keyword=k)
  search_match_placements = PremiumPlacement
    .filter(slot_type='SEARCH_MATCH', is_active=True, expires_at >= now, refunded_at is null)
    .filter(category=c)   # 필수
    .filter(region_key=r) # 필수 (또는 region_key가 빈 값이면 전체 지역)
    .filter(match_keywords가 k 포함 OR match_keywords 비어 있음)
    .order_by('paid_at')  # ASC 공정
  상단 노출 ID = search_match_placements[0..N] 의 equipment_id (N은 정책, 예 3~5)
  나머지 검색 결과 = 일반 매물 최신순
```

### 3.3 업그레이드 bump: 1~3개만 섞기 (또는 별도 섹션)

**옵션 A – 목록에 1~3개만 섞기**

```
전체 목록 = [카테고리 TOP 5칸] + [일반 매물 최신순]
  bump_candidates = EquipmentUpgrade 만료 전, bump_at 이 최근 24h 이내인 매물. order_by('-bump_at')[:3]
  최종 목록 = [TOP 5] + [bump 1개 삽입] + [일반 ...] + [bump 1개 삽입] + [일반 ...] + [bump 1개 삽입] + [일반 ...]
  (또는 단순히 TOP 5 다음에 bump 최대 3개만 이어서 배치)
```

**옵션 B – 별도 섹션**

```
상단: [카테고리 TOP 5칸]
중간: "프리미엄 업그레이드 매물" 섹션 (bump 1~3개)
이하: 일반 목록 최신순
```

**Django ORM 예시 (bump 최대 3개, TOP 다음에만)**

```python
def get_bump_equipment_ids(limit: int = 3) -> list[int]:
    from billing.models import EquipmentUpgrade
    from django.utils import timezone
    from datetime import timedelta
    threshold = timezone.now() - timedelta(hours=24)
    return list(
        EquipmentUpgrade.objects.filter(
            expires_at__gte=timezone.now(),
            bump_at__gte=threshold,
        )
        .order_by('-bump_at')
        .values_list('equipment_id', flat=True)[:limit]
    )
```

### 3.4 무료 만료: EXPIRED_HIDDEN + 1클릭 연장

- **목록/검색:** `Equipment.objects.filter(listing_status='NORMAL')` 만 사용.
- **만료 처리 크론:** `expires_at < now` 인 무료 매물은 `listing_status = 'EXPIRED_HIDDEN'` 으로 변경 (삭제 X).
- **상세 페이지:** `EXPIRED_HIDDEN` 이어도 URL로 접근 가능. 화면에 "게시가 만료되었습니다. 1클릭 연장 또는 업그레이드하세요" + 버튼 노출.

---

## 4. 관리자 기능 변경점

| 기능 | 변경 내용 |
|------|-----------|
| **PremiumPlacement** | slot_no(1~5), waitlist_rank 표시/편집. 대기열→슬롯 수동 배정. **admin_memo**, **refunded_at**, **refund_amount**, **period_adjusted_at** 필드 표시/편집. |
| **Order** | **admin_memo**, **refund_amount**, **refunded_at** 표시. 부분환불 입력 시 하위 Payment/Placement 반영 안내. |
| **Payment** | **admin_memo**, **refund_amount**, **refunded_at**. |
| **Equipment** | **listing_status** 필터 (NORMAL / EXPIRED_HIDDEN). 만료된 것만 골라 일괄 연장/복구 가능. |
| **Product** | SEARCH_TOP 제거, SEARCH_MATCH 상품 추가. 슬롯 5칸/대기열 안내. |
| **대기열 관리** | 카테고리별 대기열 목록(waitlist_rank, paid_at), 슬롯 비었을 때 1클릭 배정. |
| **전환 로그** | **ConversionEvent** 목록/필터(event_type, 기간, user). CSV 내보내기. |

---

## 5. 출시 순서(마일스톤)

| 단계 | 내용 |
|------|------|
| **M1** | DB 스키마 적용: Equipment.listing_status, PremiumPlacement(slot_no, waitlist_rank, paid_at, admin_memo, refund_*, SEARCH_MATCH), Order/Payment 환불·메모, ConversionEvent. 기존 SEARCH_TOP 데이터는 SEARCH_MATCH로 마이그레이션 또는 폐기. |
| **M2** | 카테고리 TOP 5칸 + 대기열 로직 적용. 정렬을 paid_at ASC로 전환. 목록/상세에 슬롯/대기열 안내 노출. |
| **M3** | 무료 만료 시 EXPIRED_HIDDEN 전환, 상세에서 1클릭 연장/업그레이드 CTA 및 결제 플로우. |
| **M4** | 업그레이드 bump 1~3개만 섞기(또는 별도 섹션) 적용. |
| **M5** | SEARCH_MATCH 상품 오픈, 검색 결과에서 카테고리+지역(+키워드) 매칭 노출만 허용. |
| **M6** | 관리자: 환불/기간조정/admin_memo, 대기열 배정 UI. 전환 로그(ConversionEvent) 조회/내보내기. |
| **M7** | PRO 1차: 수동 연장 결제만. 갱신 알림 → 결제 링크 → 기간 연장. |
| **M8** | PRO 2차: 정기결제(PG) 도입, is_auto_renew 및 실패 시 재시도/해지 정책. |

---

## 6. 문서/코드 반영 위치

- **기획서:** 본 문서(MONETIZATION_PLAN_V2.md)를 기준으로 기존 MONETIZATION_PLAN.md 참조용으로 유지 또는 V2 내용으로 통합.
- **모델:** `billing/models.py` 에 PremiumPlacement 확장(slot_no, waitlist_rank, paid_at, match_keywords, admin_memo, refund_*, period_adjusted_at), Order/Payment 환불·메모, ConversionEvent 추가; `equipment/models.py` 에 Equipment.listing_status(NORMAL/EXPIRED_HIDDEN) 추가.
- **마이그레이션:** 기존 Equipment 행은 `listing_status` default=NORMAL 로 자동 적용. 기존 SEARCH_TOP 데이터는 SEARCH_MATCH로 수동 마이그레이션 또는 폐기.
- **정렬/쿼리:** `billing/services/exposure_ordering.py` 에 get_category_top_equipment_ids(paid_at ASC, 슬롯 5칸+대기열), get_region_top_equipment_ids, get_search_match_equipment_ids, get_bump_equipment_ids(limit=3), merge_list_with_bump 반영.
- **관리자:** `billing/admin.py` 에 새 필드 및 ConversionEvent Admin 추가.

이 개선안을 기준으로 DB 마이그레이션과 단계별 배포를 진행하면 됩니다.
