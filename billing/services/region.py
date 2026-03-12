"""
지역키(region_key) 정규화. REGION_TOP / SEARCH_MATCH에서 표기 통일용.

- PremiumPlacement.region_key 는 Equipment.current_location 을 이 함수로 정규화한 값으로 채운다.
- "서울시/서울특별시 → 서울" 등 간단 매핑으로 검색·매칭이 안정적으로 동작하도록 한다.
"""


def normalize_region_key(s: str | None) -> str:
    """
    지역 문자열을 정규화하여 region_key 로 사용.
    공백/특수문자 정리, 표기 통일(서울시·서울특별시 → 서울), 앞 50자 반환.
    """
    if s is None:
        return ""
    s = (s or "").strip()
    # 표기 통일 (필요 시 매핑 확장)
    s = s.replace("서울특별시", "서울").replace("서울시", "서울")
    s = " ".join(s.split())  # 연속 공백 제거
    return s[:50]
