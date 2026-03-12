# direct-nara.co.kr → 굴삭기나라 리뉴얼 DB 이관 가이드

기존 굴삭기나라(direct-nara.co.kr) DB를 리뉴얼 사이트로 이관할 때 따를 설계·실무 가이드입니다.  
**이관 스크립트는 “1회성 덮기”가 아니라 “재실행 가능한 작업”으로 설계**합니다.

---

## 1. Idempotent + 추적 가능 (필수)

- **Idempotent**: `get_or_create` 또는 **이관표(legacy_id)** 기준으로 `update` → 재실행해도 중복 생성 안 됨.
- **추적 가능**: 모든 이관 데이터에 **source(direct) + source_id(기존 PK)** 저장.

### 1.1 신규 DB에 추가할 필드 (강력 추천)

| 대상 | 필드 | 용도 |
|------|------|------|
| User / Profile | `legacy_member_id` | 기존 회원 PK. 매핑·증분 이관·중복 방지 |
| Equipment | `legacy_listing_id` | 기존 매물 PK. 재import·일부만 재import 시 필수 |
| EquipmentImage | `legacy_image_id` | 기존 이미지 PK(있다면). 실패 재시도·검증용 |

이 필드가 없으면 “중복 import”, “일부만 다시 import” 시 추적이 어려워집니다.

---

## 2. 회원 식별: 전화번호만 쓰지 말 것

전화번호는 **중복·누락·형식 불량·변경** 이슈가 있으므로:

- **매핑 키**: **기존 회원 PK** (가장 안전).
- **보조 키**: 전화번호 정규화 후 유니크 처리(가능하면).

### 2.1 전화번호 정규화 (이관 전 1회)

- 공백/하이픈 제거
- `+82` → `0` 변환
- 자리수/패턴 안 맞으면 `"unknown"` 처리하고 **legacy_id로만** 연결

### 2.2 User.username

- `username = phone_normalized`가 불가하면  
  `username = f"legacy_{legacy_member_id}"` 로 안전하게 유니크 보장.

---

## 3. 이관 순서 (4단계)

### 0단계: 스냅샷(동결)

- direct DB를 **dump** 떠서 이관 기준 시점 고정.
- 운영 중 데이터가 바뀌면 결과가 매번 달라지므로, 테스트/본이관 모두 동일 스냅샷 사용 권장.

### 1단계: 회원 이관 + 매핑 테이블

- 회원 전부 생성 후 **legacy_member_id → new_user_id** 매핑 확정.
- `User.username`: `phone_normalized` 또는 `legacy_{legacy_member_id}`.
- Profile / MemberProfile 등에 `legacy_member_id` 저장.

### 2단계: 매물 이관 (배치 + 트랜잭션)

- **author**는 **매핑 테이블(legacy_member_id → user_id)** 로만 연결.
- 배치 크기: 500~2000개 단위 (서버 스펙에 따라).
- `bulk_create` + `ignore_conflicts` 또는 `update_or_create(legacy_listing_id 기준)`.
- 매물 insert 전 **카테고리/상태 기본값** 강제 세팅.

### 3단계: 이미지 이관 (매물 완료 후)

- 이미지는 시간이 오래 걸리므로 **마지막에 별도** 실행.
- URL 다운로드 또는 파일 복사 중 한 방식으로 표준화.
- **실패한 이미지만 재시도** 가능하게 하려면 “큐(테이블)” 형태로 남기면 좋음 (예: `legacy_image_id`, `status`, `retry_count`).

---

## 4. 성능/안정성 핵심 7개

1. **회원 먼저 전부 만들고 매핑 확정** 후 매물 이관.
2. 매물은 **bulk_create** 기본 (수백 개 단위면 필수).
3. **배치마다 `transaction.atomic()`**.
4. **배치마다 로그** (성공/실패/건수).
5. 매물 insert 전 **카테고리/상태 기본값** 강제 세팅.
6. **인덱스**: 처음부터 과도하게 잡지 말 것. 대량 insert 느려짐. 큰 테이블은 **이관 후 인덱스 추가**가 더 빠른 경우 많음.
7. **검증 쿼리**를 스크립트에 포함:
   - 총 회원수, 총 매물수
   - 랜덤 10명 `legacy_member_id` 뽑아서 “기존 매물수 vs 신규 매물수” 비교.

---

## 5. 비밀번호/로그인 정책 (이관 전 결론)

- 기존 비밀번호를 가져올 수 없으면:
  - `set_unusable_password()` 적용.
  - **로그인: 전화번호 + 인증코드(SMS)** 로 전환.
  - 첫 로그인 시 비밀번호 설정 유도(선택).
- 굴삭기나라 특성상 전화번호 인증 로그인은 사용자 저항이 낮고 CS도 줄어듦.

---

## 6. 운영 중 이관 (트래픽 있는 경우)

완전 셧다운이 어렵다면 **2회 이관** 전략:

1. **1차**: 전체 이관(스냅샷 기준).
2. 이후 며칠 운영하며 차이 발생.
3. **2차**: **legacy_*_id** 기준으로 **변경분만** 추가/업데이트(증분 이관).

이를 가능하게 하는 것이 `legacy_member_id`, `legacy_listing_id`, `legacy_image_id` 입니다.

---

## 7. 최종 정리

- **연결키**: **기존 PK(legacy_*_id)**. 전화번호는 “사람 찾는 보조키”.
- **이관 설계**: 재실행 가능(idempotent) + 추적 가능(source_id/legacy_id).
- **구현 핵심**: legacy_id 기반 매핑 + 배치 bulk_create + 이미지 분리(실패 재시도 구조).

이 문서는 이관 스크립트 작성·테스트·재실행 시 기준으로 사용합니다.
