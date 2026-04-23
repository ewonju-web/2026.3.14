from django import template
import re

register = template.Library()


I18N = {
    "ko": {
        "lang_label": "한국어",
        "nav_market": "중고매물",
        "nav_jobs": "구인구직",
        "nav_attachment": "어태치먼트",
        "nav_youtube": "정비유튜브",
        "nav_parts_as": "부품/AS",
        "nav_soil": "현장 자재 나눔",
        "nav_chat": "채팅",
        "nav_mypage": "마이페이지",
        "nav_login": "로그인",
        "nav_logout": "로그아웃",
        "nav_signup": "회원가입",
        "nav_register": "매물등록",
        "mobile_home": "홈",
        "mobile_listings": "매물",
        "mobile_jobs": "구인구직",
        "mobile_my": "마이",
        "service_all": "전체 서비스",
        "service_trade": "장비 거래",
        "service_menu": "서비스",
        "service_market_home": "중고매물 홈",
        "mypage_title": "마이페이지",
        "mypage_favorites": "찜한 매물",
        "mypage_my_listings": "내가 올린 매물",
        "account_delete": "회원 탈퇴",
        "account_delete_cancel": "취소",
        "account_delete_confirm": "정말 탈퇴하시겠습니까?",
        "account_delete_submit": "정말 탈퇴합니다",
    },
    "en": {
        "lang_label": "English",
        "nav_market": "Listings",
        "nav_jobs": "Jobs",
        "nav_attachment": "Attachments",
        "nav_youtube": "Repair YouTube",
        "nav_parts_as": "Parts/AS",
        "nav_soil": "Site Material Share",
        "nav_chat": "Chats",
        "nav_mypage": "My Page",
        "nav_login": "Login",
        "nav_logout": "Logout",
        "nav_signup": "Sign Up",
        "nav_register": "Post Listing",
        "mobile_home": "Home",
        "mobile_listings": "Listings",
        "mobile_jobs": "Jobs",
        "mobile_my": "My",
        "service_all": "All Services",
        "service_trade": "Equipment Trade",
        "service_menu": "Services",
        "service_market_home": "Listings Home",
        "mypage_title": "My Page",
        "mypage_favorites": "Favorites",
        "mypage_my_listings": "My Listings",
        "account_delete": "Delete Account",
        "account_delete_cancel": "Cancel",
        "account_delete_confirm": "Are you sure you want to delete your account?",
        "account_delete_submit": "Yes, delete my account",
    },
    "ru": {
        "lang_label": "Русский",
        "nav_market": "Объявления",
        "nav_jobs": "Работа",
        "nav_attachment": "Навесное",
        "nav_youtube": "YouTube по ремонту",
        "nav_parts_as": "Запчасти/Сервис",
        "nav_soil": "Раздача стройматериалов",
        "nav_chat": "Чаты",
        "nav_mypage": "Моя страница",
        "nav_login": "Войти",
        "nav_logout": "Выйти",
        "nav_signup": "Регистрация",
        "nav_register": "Добавить объявление",
        "mobile_home": "Главная",
        "mobile_listings": "Объявления",
        "mobile_jobs": "Работа",
        "mobile_my": "Мой",
        "service_all": "Все сервисы",
        "service_trade": "Техника",
        "service_menu": "Сервисы",
        "service_market_home": "Главная объявлений",
        "mypage_title": "Моя страница",
        "mypage_favorites": "Избранные объявления",
        "mypage_my_listings": "Мои объявления",
        "account_delete": "Удалить аккаунт",
        "account_delete_cancel": "Отмена",
        "account_delete_confirm": "Вы уверены, что хотите удалить аккаунт?",
        "account_delete_submit": "Да, удалить аккаунт",
    },
    "vi": {
        "lang_label": "Tiếng Việt",
        "nav_market": "Tin đăng",
        "nav_jobs": "Việc làm",
        "nav_attachment": "Phụ kiện",
        "nav_youtube": "YouTube sửa chữa",
        "nav_parts_as": "Phụ tùng/AS",
        "nav_soil": "Chia sẻ vật liệu công trường",
        "nav_chat": "Chat",
        "nav_mypage": "Trang của tôi",
        "nav_login": "Đăng nhập",
        "nav_logout": "Đăng xuất",
        "nav_signup": "Đăng ký",
        "nav_register": "Đăng bán",
        "mobile_home": "Trang chủ",
        "mobile_listings": "Tin đăng",
        "mobile_jobs": "Việc làm",
        "mobile_my": "Của tôi",
        "service_all": "Tất cả dịch vụ",
        "service_trade": "Giao dịch thiết bị",
        "service_menu": "Dịch vụ",
        "service_market_home": "Trang tin đăng",
        "mypage_title": "Trang của tôi",
        "mypage_favorites": "Tin đã lưu",
        "mypage_my_listings": "Tin tôi đã đăng",
        "account_delete": "Xóa tài khoản",
        "account_delete_cancel": "Hủy",
        "account_delete_confirm": "Bạn có chắc muốn xóa tài khoản?",
        "account_delete_submit": "Tôi đồng ý xóa tài khoản",
    },
}


@register.filter(name="tr")
def translate(lang_code, key):
    lang = (lang_code or "ko").strip().lower()
    if lang not in I18N:
        lang = "ko"
    return I18N.get(lang, I18N["ko"]).get(key, I18N["ko"].get(key, key))


@register.filter
def format_phone(value: str) -> str:
    """
    휴대폰 번호를 010-0000-0000 형식으로 변환.
    - 숫자만 남기고, 10~11자리만 처리
    - 그 외 길이는 원본 그대로 반환
    """
    if not value:
        return ""
    raw = str(value)
    digits = re.sub(r"[^0-9]", "", raw)

    # 값 안에 전화번호가 2개 이상(개행/공백 포함) 섞여 들어오는 경우가 있어,
    # 숫자 길이가 10/11이 아니더라도 "첫 번째 정상 전화번호"만 뽑아 포맷합니다.
    m010 = re.search(r"(010\d{8})", digits)
    if m010:
        d = m010.group(1)
        return f"{d[0:3]}-{d[3:7]}-{d[7:11]}"

    m10 = re.search(r"(\d{10})", digits)
    if m10:
        d = m10.group(1)
        return f"{d[0:3]}-{d[3:6]}-{d[6:10]}"

    # 기존 동작(입력 자체가 이미 포맷된 케이스)에 최대한 호환
    if len(digits) == 11 and digits.startswith("010"):
        return f"{digits[0:3]}-{digits[3:7]}-{digits[7:11]}"
    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"

    return raw


@register.filter
def user_phone(user) -> str:
    """
    User에서 Profile.phone을 안전하게 꺼냄.
    OneToOne Profile이 없는 계정도 예외 없이 빈 문자열 반환.
    """
    if not user:
        return ""
    try:
        profile = getattr(user, "profile", None)
        if not profile:
            return ""
        return (getattr(profile, "phone", None) or "").strip()
    except Exception:
        return ""


@register.filter
def equipment_row_contact(equipment):
    """
    목록(더보기 표) 등록인/연락처 표시.
    작성자 Profile.phone → 없으면 equipment_detail과 동일한 sibling(동일 모델·가격·위치·등록일) fallback.
    """
    if not equipment:
        return "-"
    from equipment.models import Equipment

    if equipment.author_id:
        try:
            profile = getattr(equipment.author, "profile", None)
            if profile:
                ph = (getattr(profile, "phone", None) or "").strip()
                if ph and any(ch.isdigit() for ch in ph):
                    return format_phone(ph)
        except Exception:
            pass
        un = (getattr(equipment.author, "username", None) or "").strip()
        return un if un else "-"

    sibling_qs = (
        Equipment.objects.visible()
        .select_related("author__profile")
        .exclude(pk=equipment.pk)
        .exclude(author__isnull=True)
        .filter(
            model_name=equipment.model_name,
            listing_price=equipment.listing_price,
            current_location=equipment.current_location,
            created_at__date=equipment.created_at.date(),
        )
        .order_by("-created_at")
    )
    for sibling in sibling_qs[:10]:
        sp = getattr(getattr(sibling, "author", None), "profile", None)
        sibling_phone = getattr(sp, "phone", None) if sp else None
        if not sibling_phone:
            continue
        ph = str(sibling_phone).strip()
        if ph and not any(ch.isdigit() for ch in ph):
            continue
        return format_phone(ph)
    return "-"

