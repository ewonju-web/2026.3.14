# 차량번호(vehicle_number) 필드 · 뱃지 체크리스트

## 1) 필드명 통일 (서버 업로드 필드와 충돌 없음)

| 구분 | 필드명 | 비고 |
|------|--------|------|
| 모델 | `vehicle_number` | Equipment.vehicle_number |
| 폼 | `vehicle_number` | EquipmentForm 필드/name="vehicle_number" |
| 템플릿 폼 | `form.vehicle_number` | input name은 Django가 vehicle_number로 렌더 |
| 표시(상세/리스트/마이페이지) | `equipment.vehicle_number` / `e.vehicle_number` | 동일 필드 참조 |
| 파일 업로드 | `images` (별도) | request.FILES.getlist('images')와 충돌 없음 |

→ **전부 `vehicle_number`로 통일됨.**

---

## 2) 기존 데이터 / 마이그레이션 안전

- **모델**: `vehicle_number = models.CharField(max_length=30, blank=True, default="", ...)`
- **마이그레이션 0025**: `AddField(..., default='', blank=True)` → 기존 행에 빈 문자열 적용
- **적용 후 확인**: `manage.py check` 통과, admin/목록/상세에서 오류 없음

---

## 3) 뱃지 위치 · 표시 규칙

| 화면 | 위치 | 문구 |
|------|------|------|
| **리스트 카드** (모바일·PC) | 가격 옆 1곳만 | "번호등록" |
| **상세** | 제목/가격 근처 (팝니다 뱃지 옆) | "번호등록" |
| **문구** | 인증/확인/검증 등 과장 표현 사용 금지 | "번호등록"만 사용 |

- 리스트: 썸네일 상단이 아닌 **가격 옆** 한 곳에만 표시 (현재 구현 유지).
- 상세: 판매금액 블록 위, 팝니다 뱃지 옆에만 표시.
