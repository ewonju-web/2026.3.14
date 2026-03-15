# -*- coding: utf-8 -*-
"""
휴대폰 인증: 6자리 인증번호 발송·검증 (3분 유효, 5회 시도 제한, 재발송 30초 제한).
문자 발송은 SMS API 연동 시 send_sms() 구현만 교체하면 됨.
"""
import random
import time
from django.core.cache import cache
from django.conf import settings

CACHE_PREFIX = "phone_verify:"
CODE_VALID_SECONDS = 180  # 3분
RESEND_COOLDOWN_SECONDS = 30
MAX_VERIFY_ATTEMPTS = 5


def _cache_key(phone_norm: str) -> str:
    return f"{CACHE_PREFIX}{phone_norm}"


def _make_code() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(6))


def send_sms(phone_norm: str, message: str) -> bool:
    """
    문자 발송. 실제 연동 시 여기만 수정.
    - 문자 업체 선택 → 계정·발신번호 등록 → API 키 발급 → 이 함수에 연동.
    """
    # 스텁: 설정에 SMS API 키가 있으면 실제 발송 시도, 없으면 로그만 (개발 시 콘솔 출력)
    api_key = getattr(settings, "SMS_API_KEY", None) or getattr(settings, "SENS_SERVICE_KEY", None)
    if api_key:
        # TODO: NHN SENS / 알리고 / Twilio 등 실제 API 호출
        # return _send_via_nhn(phone_norm, message) 등
        pass
    if getattr(settings, "DEBUG", True):
        print(f"[SMS 스텁] 수신: {phone_norm}, 내용: {message}")
    return True


def send_code(phone_norm: str) -> tuple[bool, str]:
    """
    인증번호 발송. 재발송 30초 제한 적용.
    Returns: (success, error_message)
    """
    key = _cache_key(phone_norm)
    data = cache.get(key)
    now = time.time()
    if data and (now - data.get("last_send_at", 0) < RESEND_COOLDOWN_SECONDS):
        return False, "재발송은 30초 이후에 가능합니다."
    code = _make_code()
    cache.set(
        key,
        {
            "code": code,
            "sent_at": now,
            "last_send_at": now,
            "verify_attempts": 0,
        },
        timeout=CODE_VALID_SECONDS,
    )
    msg = f"[굴삭기나라] 인증번호 [{code}] 3분 내 입력해 주세요."
    if not send_sms(phone_norm, msg):
        return False, "문자 발송에 실패했습니다. 잠시 후 다시 시도해 주세요."
    return True, ""


def verify_code(phone_norm: str, code: str) -> tuple[bool, str]:
    """
    인증번호 검증. 5회 초과 시 실패.
    Returns: (success, error_message)
    """
    key = _cache_key(phone_norm)
    data = cache.get(key)
    if not data:
        return False, "인증번호가 만료되었습니다. 다시 발송해 주세요."
    attempts = data.get("verify_attempts", 0) + 1
    if attempts > MAX_VERIFY_ATTEMPTS:
        cache.delete(key)
        return False, "인증 시도 횟수를 초과했습니다. 인증번호를 다시 발송해 주세요."
    if data.get("code") != code.strip():
        data["verify_attempts"] = attempts
        remain = int(data.get("sent_at", 0) + CODE_VALID_SECONDS - time.time())
        cache.set(key, data, timeout=max(1, remain))
        return False, "인증번호가 일치하지 않습니다."
    cache.delete(key)
    return True, ""
