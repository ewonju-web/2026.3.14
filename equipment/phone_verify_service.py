# -*- coding: utf-8 -*-
"""
휴대폰 인증: 6자리 인증번호 발송·검증 (3분 유효, 5회 시도 제한, 재발송 30초 제한).
문자 발송은 Solapi(SOLAPI_*) 설정 시 실제 발송, 미설정 시 DEBUG에서만 콘솔 스텁.
"""
import logging
import random
import time
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

CACHE_PREFIX = "phone_verify:"
CODE_VALID_SECONDS = 180  # 3분
RESEND_COOLDOWN_SECONDS = 30
MAX_VERIFY_ATTEMPTS = 5


def _cache_key(phone_norm: str) -> str:
    return f"{CACHE_PREFIX}{phone_norm}"


def _make_code() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(6))


def _solapi_configured() -> bool:
    key = (getattr(settings, "SOLAPI_API_KEY", "") or "").strip()
    secret = (getattr(settings, "SOLAPI_API_SECRET", "") or "").strip()
    sender = (getattr(settings, "SOLAPI_SENDER", "") or "").strip()
    return bool(key and secret and sender)


def _solapi_failure_detail(resp) -> str:
    """SendMessageResponse에서 사용자·로그용 실패 사유 문자열 추출."""
    parts: list[str] = []
    for fm in resp.failed_message_list or []:
        sm = (getattr(fm, "status_message", None) or "").strip()
        sc = (getattr(fm, "status_code", None) or "").strip()
        if sm:
            parts.append(f"{sc}: {sm}" if sc else sm)
    for mi in resp.message_list or []:
        sm = (getattr(mi, "status_message", None) or "").strip()
        if sm:
            parts.append(sm)
    if not parts and getattr(resp, "group_info", None) is not None:
        log = getattr(resp.group_info, "log", None) or []
        if log:
            parts.append(str(log[-1]))
    return "; ".join(parts) if parts else "Solapi에서 발송이 실패했습니다. 콘솔 전송 로그의 사유를 확인해 주세요."


def _send_via_solapi(phone_norm: str, message: str) -> None:
    """Solapi API 호출. 실패 시 예외 발생."""
    from solapi import SolapiMessageService
    from solapi.error.MessageNotReceiveError import MessageNotReceivedError
    from solapi.model import RequestMessage

    api_key = (getattr(settings, "SOLAPI_API_KEY", "") or "").strip()
    api_secret = (getattr(settings, "SOLAPI_API_SECRET", "") or "").strip()
    from_num = (getattr(settings, "SOLAPI_SENDER", "") or "").strip()
    if not api_key or not api_secret or not from_num:
        raise ValueError("SOLAPI_API_KEY, SOLAPI_API_SECRET, SOLAPI_SENDER를 모두 설정하세요.")

    service = SolapiMessageService(api_key=api_key, api_secret=api_secret)
    req = RequestMessage(from_=from_num, to=phone_norm, text=message)
    try:
        resp = service.send(req)
    except MessageNotReceivedError as e:
        msgs = [
            (getattr(fm, "status_message", None) or "").strip()
            for fm in (e.failed_messages or [])
        ]
        msgs = [m for m in msgs if m]
        raise RuntimeError(msgs[0] if msgs else str(e)) from e

    cnt = resp.group_info.count
    # Solapi는 접수 직후 sent_* 값이 0일 수 있으므로 registered_success도 성공으로 본다.
    sent_ok = (
        (cnt.sent_success or 0) > 0
        or (cnt.sent_pending or 0) > 0
        or (cnt.registered_success or 0) > 0
    )
    if cnt.total > 0 and not sent_ok:
        detail = _solapi_failure_detail(resp)
        logger.warning(
            "Solapi 발송 단계 실패 (끝번호 ****%s, group_id=%s, count=%s, detail=%s)",
            phone_norm[-4:] if len(phone_norm) >= 4 else "?",
            resp.group_info.group_id,
            cnt.model_dump() if hasattr(cnt, "model_dump") else cnt,
            detail,
        )
        raise RuntimeError(detail)

    gid = getattr(getattr(resp, "group_info", None), "group_id", None)
    logger.info(
        "Solapi SMS 발송 성공 (끝번호 ****%s, group_id=%s)",
        phone_norm[-4:] if len(phone_norm) >= 4 else "?",
        gid,
    )


def send_sms(phone_norm: str, message: str) -> tuple[bool, str]:
    """
    문자 발송.
    - Solapi 설정이 있으면 실제 발송
    - 없으면 DEBUG일 때만 콘솔 스텁 후 (True, ""), 운영에서는 (False, 사유)
    Returns: (성공 여부, 실패 시 사유 문자열)
    """
    if _solapi_configured():
        try:
            _send_via_solapi(phone_norm, message)
            return True, ""
        except Exception as e:
            logger.exception("Solapi SMS 발송 실패: %s", e)
            err = str(e).strip()
            if not err:
                err = "문자 발송에 실패했습니다. 잠시 후 다시 시도해 주세요."
            return False, err

    if getattr(settings, "DEBUG", True):
        print(f"[SMS 스텁] 수신: {phone_norm}, 내용: {message}")
        return True, ""

    logger.warning("SOLAPI 미설정으로 SMS를 보낼 수 없습니다. (DEBUG=False)")
    return False, "문자를 보낼 수 없습니다. 관리자에게 문의해 주세요."


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

    if not _solapi_configured() and not getattr(settings, "DEBUG", False):
        return (
            False,
            "SMS 발신번호가 등록되지 않았습니다. 서버 .env의 SOLAPI_SENDER에 "
            "Solapi 콘솔에 등록한 발신번호(01012345678 형식)를 입력한 뒤 서버를 재시작해 주세요.",
        )

    code = _make_code()
    site = getattr(settings, "SITE_NAME", "굴삭기나라")
    msg = f"[{site}] 인증번호 [{code}] 3분 내 입력해 주세요."
    ok, sms_err = send_sms(phone_norm, msg)
    if not ok:
        return False, sms_err or "문자 발송에 실패했습니다. 잠시 후 다시 시도해 주세요."

    # 발송 성공 후에만 캐시 (실패 시 잘못된 코드만 남는 문제 방지)
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


def send_verification_sms(phone_raw: str) -> tuple[bool, str]:
    """
    테스트·디버그용: Solapi로 테스트 문자 1통 발송 (shell에서 확인용).

    >>> send_verification_sms('01012345678')

    Returns:
        (성공 여부, 메시지)
    """
    from equipment.claim_utils import normalize_phone_digits

    to = normalize_phone_digits(phone_raw)
    if not to or len(to) < 10 or not to.startswith("01"):
        return False, "올바른 휴대폰 번호(010…)를 입력하세요."

    if not _solapi_configured():
        return False, "SOLAPI_API_KEY, SOLAPI_API_SECRET, SOLAPI_SENDER를 .env에 설정하세요."

    site = getattr(settings, "SITE_NAME", "굴삭기나라")
    body = f"[{site}] Solapi SMS 연동 테스트입니다."
    try:
        _send_via_solapi(to, body)
        return True, "발송 성공"
    except Exception as e:
        logger.exception("send_verification_sms 실패: %s", e)
        return False, str(e)
