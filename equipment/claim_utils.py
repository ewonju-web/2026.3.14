"""미연결 매물 ↔ 본인 전화번호 매칭용 유틸."""

import re


def normalize_phone_digits(phone: str | None) -> str:
    """숫자만 남겨 비교 키로 사용 (하이픈·공백 제거)."""
    if not phone:
        return ""
    return re.sub(r"\D", "", str(phone).strip())
