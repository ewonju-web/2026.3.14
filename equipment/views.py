from equipment.forms import UserSignupForm
from django.contrib.auth.models import User
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q, Min, Max, Avg, Count, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
import json

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from .models import Equipment, JobPost, Part, EquipmentImage, PartImage, PartsShop, YoutubeContent, EquipmentFavorite, PartFavorite, Comment, DeletedListingLog, Profile
from soil.models import SoilPost
from .forms import EquipmentForm, EquipmentEditForm
from .premium_utils import (
    is_user_premium,
    get_free_listing_count,
    FREE_LISTING_LIMIT,
    get_premium_user_ids,
    get_premium_equipment_rotation,
    get_premium_equipment_sidebar,
    pad_premium_sidebar_slots,
    PREMIUM_SIDEBAR_INDEX_TOTAL,
    PREMIUM_SIDEBAR_EXPERT_TITLE_BY_CATEGORY,
)
from .claim_utils import normalize_phone_digits
from .listing_filters import (
    exclude_excavator_misclassified_for_non_excavator_tabs,
    exclude_attachment_like_from_non_attachment_tabs,
    filter_attachment_tab,
)


def _image_hash_from_upload(uploaded_file):
    """업로드 파일 내용으로 MD5 해시 (동일 사진 재업로드 감지)."""
    import hashlib
    try:
        uploaded_file.seek(0)
        return hashlib.md5(uploaded_file.read()).hexdigest()
    except Exception:
        return ""


def _image_hash_from_equipment(equipment):
    """매물 대표 사진(첫 번째) 해시 (삭제 시 로그용)."""
    import hashlib
    first = equipment.images.first()
    if not first or not first.image:
        return ""
    try:
        with first.image.open("rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def _get_profile_phone_verified(user):
    """휴대폰 본인인증 여부. Profile 없으면 생성 후 False."""
    if not user or not user.is_authenticated:
        return False
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)
    return getattr(profile, 'phone_verified', False)


def _user_has_social_account(user):
    """소셜(카카오/네이버 등) 로그인으로 가입·연동된 계정인지 여부. 아이디/비밀번호만 쓰는 회원은 False."""
    if not user or not user.is_authenticated:
        return False
    try:
        from allauth.socialaccount.models import SocialAccount
        return SocialAccount.objects.filter(user=user).exists()
    except Exception:
        return False


def _require_phone_verified(request, next_url=None):
    """
    매물 등록·유료 결제 등 전 휴대폰 인증 필수.
    단, 아이디/비밀번호로 가입한 회원(소셜 연동 없음)은 본인인증 생략.
    인증 필요하고 안 됐으면 redirect 응답 반환, 통과 시 None.
    """
    if not request.user.is_authenticated:
        return redirect('login')
    # 아이디·비밀번호로만 가입한 회원은 본인인증 불필요
    if not _user_has_social_account(request.user):
        return None
    if _get_profile_phone_verified(request.user):
        return None
    from urllib.parse import quote
    from django.urls import reverse
    next_path = next_url or request.get_full_path()
    return redirect(reverse('phone_verify') + '?next=' + quote(next_path, safe=''))


def _build_location_text(region_sido: str, region_sigungu: str) -> str:
    """매물 위치 문자열: 시/도·시/군/구만 사용 (상세 주소 입력 없음)."""
    sido = (region_sido or '').strip()
    sigungu = (region_sigungu or '').strip()
    if sido and sigungu:
        return f"{sido} {sigungu}"
    return sido or ''


def _is_excavator_tire_5_6_filter(sub_type: str, weight_class: str) -> bool:
    """굴삭기 상세검색에서 '타이어식 5~6 ton' 선택 여부."""
    return sub_type == 'EXC_TIRE' and weight_class == 'EXC_TIRE_LE_6'


def _legacy_excavator_tire_5_6_q() -> Q:
    """
    레거시 데이터 호환:
    - 예전 이관 데이터는 sub_type/weight_class 코드가 비어있거나 잘못된 경우가 있어
      모델명 패턴(EW60/HW60/DX55W/06W 등)도 함께 검색한다.
    """
    return Q(
        model_name__iregex=(
            r"(EW\s*60|EW\s*55|HW\s*60|DX\s*55\s*W|R\s*555\s*W|"
            r"\b55\s*W(?:I)?\b|\b0?6\s*W\b)"
        )
    )


def legacy_redirect_equipment_uid(request, uid):
    """
    구형 매물 URL → /equipment/<pk>/ (301).
    /viewsale/굴삭기{uid}, /attachment/{uid} 등. uid는 이관 시 legacy_listing_id 우선, 없으면 pk로 조회.
    """
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        raise Http404()
    eq = Equipment.objects.filter(legacy_listing_id=uid_int).first()
    if eq:
        return redirect("equipment_detail", pk=eq.pk, permanent=True)
    if Equipment.objects.filter(pk=uid_int).exists():
        return redirect("equipment_detail", pk=uid_int, permanent=True)
    raise Http404()


def legacy_redirect_job_uid(request, uid):
    """구형 /job/{uid}/ → /jobs/<pk>/ (301). uid는 legacy_guin_uid 우선, 없으면 pk."""
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        raise Http404()
    job = JobPost.objects.filter(legacy_guin_uid=uid_int).first()
    if job:
        return redirect("job_detail", pk=job.pk, permanent=True)
    if JobPost.objects.filter(pk=uid_int).exists():
        return redirect("job_detail", pk=uid_int, permanent=True)
    raise Http404()


def legacy_redirect_community_to_board(request, uid):
    """구형 /community/{uid}/ → /board/{uid}/ (301)."""
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        raise Http404()
    return redirect("board_detail", pk=uid_int, permanent=True)


def board_post_detail(request, pk):
    """
    신규 커뮤니티 상세 URL (/board/<pk>/).
    게시판 모델 연동 전까지는 404 (구 URL 301 대상만 유효).
    """
    raise Http404()


# [1] 메인 페이지 (키워드 + 정렬만)
def index(request):
    query = (request.GET.get('q', '') or '').strip()
    sort = (request.GET.get('sort', '') or 'new').strip().lower()
    if sort not in ('price_asc', 'price_desc', 'year_desc', 'new'):
        sort = 'new'
    filter_category = (request.GET.get('category', '') or '').strip().lower()  # excavator, forklift, dump, loader, etc
    valid_categories = ('excavator', 'forklift', 'dump', 'loader', 'crane', 'attachment', 'other')
    # ?category= (빈 값) → "전체" 명시: 세션에 저장된 기종을 쓰지 않음
    if 'category' in request.GET and not (request.GET.get('category') or '').strip():
        request.session.pop('last_equipment_category', None)
    # URL에 category 키가 없으면(예: / 또는 리다이렉트로 쿼리만 남은 경우) 직전 기종을 유지해 기종이 섞여 보이지 않게 함
    elif 'category' not in request.GET:
        last_category = (request.session.get('last_equipment_category') or '').strip().lower()
        if last_category in valid_categories:
            filter_category = last_category
    # 검색어는 있는데 위에서도 비어 있으면(예외 경로) 세션 기종 유지
    elif not filter_category and query:
        last_category = (request.session.get('last_equipment_category') or '').strip().lower()
        if last_category in valid_categories:
            filter_category = last_category
    # 그래도 category가 비어있다면, 검색어에 카테고리 키워드가 있는 경우 자동으로 매핑한다.
    if not filter_category and query:
        q = query.lower()
        if any(k in q for k in ("굴삭기", "excavator")):
            filter_category = "excavator"
        elif any(k in q for k in ("지게차", "forklift", "리프트")):
            filter_category = "forklift"
        elif any(k in q for k in ("덤프트럭", "덤프", "dump truck", "dump")):
            filter_category = "dump"
        elif any(k in q for k in ("로더", "휠로더", "wheel loader", "loader")):
            filter_category = "loader"
        elif any(k in q for k in ("크레인", "crane")):
            filter_category = "crane"
        elif any(k in q for k in ("어태치", "attachment")):
            filter_category = "attachment"
    if filter_category in valid_categories:
        request.session['last_equipment_category'] = filter_category

    # 상세 검색용 파라미터 (굴삭기/지게차 전용)
    maker = (request.GET.get('maker', '') or '').strip()
    sub_type = (request.GET.get('sub_type', '') or '').strip()
    weight_class = (request.GET.get('weight_class', '') or '').strip()
    model = (request.GET.get('model', '') or '').strip()
    year_min = (request.GET.get('year_min') or '').strip()
    year_max = (request.GET.get('year_max') or '').strip()
    region_sido = (request.GET.get('region_sido', '') or '').strip()
    region_sigungu = (request.GET.get('region_sigungu', '') or '').strip()
    mast_type = (request.GET.get('mast_type', '') or '').strip()
    premium_only = request.GET.get('premium_only') == '1'
    # 상세검색 실행 후에는 목록 화면에서 상세검색 바를 숨기고 정렬만 남긴다.
    hide_advanced_filters = request.GET.get('expand') == '1' or any(
        bool(v) for v in (
            maker,
            sub_type,
            weight_class,
            model,
            year_min,
            year_max,
            region_sido,
            region_sigungu,
            mast_type,
        )
    )

    # 목록/검색: NORMAL만 노출(EXPIRED_HIDDEN 제외). 상세 직접 URL은 별도 허용.
    equipment_list = Equipment.objects.visible()
    if filter_category in valid_categories:
        if filter_category == "attachment":
            equipment_list = filter_attachment_tab(equipment_list)
        else:
            equipment_list = equipment_list.filter(equipment_type=filter_category)
    # 지게차·덤프·로더 탭: DB 오분류로 굴삭기가 섞이지 않도록 EXC_*·모델 패턴 제외
    equipment_list = exclude_excavator_misclassified_for_non_excavator_tabs(
        equipment_list, filter_category
    )
    # 채버켓 등 어태치: 다른 기종 탭에 나오지 않고 어태치먼트 탭에서만 보이도록
    equipment_list = exclude_attachment_like_from_non_attachment_tabs(
        equipment_list, filter_category
    )

    if query:
        lookups = (
            Q(model_name__icontains=query) |
            Q(manufacturer__icontains=query) |
            Q(current_location__icontains=query)
        )
        q_num = query.replace(',', '').replace('만원', '').replace('원', '').strip()
        if q_num.isdigit():
            lookups |= Q(listing_price=int(q_num))
            # 네 자리 숫자면 년식으로도 검색 (예: 2015 → 2015년식)
            if len(q_num) == 4 and 1980 <= int(q_num) <= 2030:
                lookups |= Q(year_manufactured=int(q_num))
        equipment_list = equipment_list.filter(lookups).distinct()

    # ── 상세 필터 (굴삭기/지게차) ────────────────────────────────
    if maker:
        equipment_list = equipment_list.filter(manufacturer__iexact=maker)

    if model:
        equipment_list = equipment_list.filter(model_name__icontains=model)

    # 연식 범위
    if year_min:
        try:
            year_min_int = int(year_min)
            equipment_list = equipment_list.filter(year_manufactured__gte=year_min_int)
        except (TypeError, ValueError):
            pass
    if year_max:
        try:
            year_max_int = int(year_max)
            equipment_list = equipment_list.filter(year_manufactured__lte=year_max_int)
        except (TypeError, ValueError):
            pass

    # 지역 (시/도, 시/군/구)
    if region_sido:
        equipment_list = equipment_list.filter(region_sido=region_sido)
    if region_sigungu:
        equipment_list = equipment_list.filter(region_sigungu=region_sigungu)

    # 카테고리별 세부 필터
    if filter_category == 'excavator':
        if sub_type:
            if _is_excavator_tire_5_6_filter(sub_type, weight_class):
                equipment_list = equipment_list.filter(
                    Q(sub_type=sub_type) | _legacy_excavator_tire_5_6_q()
                )
            else:
                equipment_list = equipment_list.filter(sub_type=sub_type)
        if weight_class:
            if _is_excavator_tire_5_6_filter(sub_type, weight_class):
                equipment_list = equipment_list.filter(
                    Q(weight_class=weight_class) | _legacy_excavator_tire_5_6_q()
                )
            else:
                equipment_list = equipment_list.filter(weight_class=weight_class)
    elif filter_category == 'forklift':
        if sub_type:
            equipment_list = equipment_list.filter(sub_type=sub_type)
        if weight_class:
            equipment_list = equipment_list.filter(weight_class=weight_class)
        if mast_type:
            equipment_list = equipment_list.filter(mast_type=mast_type)
    # 덤프트럭: 제조사(maker)는 위에서 적용됨, 톤수는 코드 정확 일치
    elif filter_category == 'dump':
        if weight_class:
            equipment_list = equipment_list.filter(weight_class=weight_class)
    # 로더/크레인/어태치먼트/기타: 중량 자유 입력(icontains)
    elif filter_category in ('loader', 'crane', 'attachment', 'other'):
        if weight_class:
            equipment_list = equipment_list.filter(weight_class__icontains=weight_class)

    # 정렬: price_asc / price_desc / year_desc / new(기본, 끌어올리기 반영)
    if sort == 'price_asc':
        equipment_list = equipment_list.order_by('listing_price')
    elif sort == 'price_desc':
        equipment_list = equipment_list.order_by('-listing_price')
    elif sort == 'year_desc':
        equipment_list = equipment_list.order_by('-year_manufactured')
    else:
        equipment_list = equipment_list.annotate(
            effective_order=Coalesce(F('last_bumped_at'), F('created_at'))
        ).order_by('-effective_order')

    premium_author_ids = set(get_premium_user_ids())
    if premium_only:
        equipment_list = equipment_list.filter(author_id__in=premium_author_ids)

    # 목록 상단 노출용 총 건수/라벨
    total_count = equipment_list.count()
    has_detail_filters = any(
        bool(v) for v in (
            maker,
            sub_type,
            weight_class,
            model,
            year_min,
            year_max,
            region_sido,
            region_sigungu,
            mast_type,
        )
    )
    if premium_only and not query and not has_detail_filters:
        total_count_label = "유료회원"
    elif query or has_detail_filters:
        total_count_label = "검색결과"
    elif filter_category in valid_categories:
        category_label_map = {
            "excavator": "굴삭기",
            "forklift": "지게차",
            "dump": "덤프트럭",
            "loader": "스키로더/로더",
            "crane": "크레인",
            "attachment": "어태치먼트",
            "other": "기타 중장비",
        }
        total_count_label = category_label_map.get(filter_category, "전체")
    else:
        total_count_label = "전체"

    equipment_list = equipment_list.select_related('author__profile')

    # 기본 최신 목록에서만 유료 회원 매물을 상단 우선 배치
    # (상세검색/정렬 결과에서는 사용자가 선택한 정렬 순서를 그대로 유지)
    if sort == 'new' and not hide_advanced_filters and not query:
        equipment_list = list(equipment_list)
        equipment_list = [e for e in equipment_list if e.author_id in premium_author_ids] + [
            e for e in equipment_list if e.author_id not in premium_author_ids
        ]
    premium_author_ids = list(premium_author_ids)  # 템플릿에서 프리미엄 배지용

    favorited_ids = set()
    if request.user.is_authenticated:
        favorited_ids = set(EquipmentFavorite.objects.filter(user=request.user).values_list('equipment_id', flat=True))

    # 유료 회원 매물: 첫 화면 로테이션(캐러셀 슬라이드당 6건, 여러 슬라이드 자동 순환), 우측 고정 배너용
    premium_rotation_list = get_premium_equipment_rotation(limit=18, equipment_type=filter_category or None)
    premium_rotation_chunks = [
        premium_rotation_list[i : i + 6]
        for i in range(0, len(premium_rotation_list), 6)
        if premium_rotation_list[i : i + 6]
    ]
    premium_sidebar_list = get_premium_equipment_sidebar(
        limit=PREMIUM_SIDEBAR_INDEX_TOTAL, equipment_type=filter_category or None
    )
    premium_sidebar_slots = pad_premium_sidebar_slots(
        premium_sidebar_list, PREMIUM_SIDEBAR_INDEX_TOTAL
    )
    premium_sidebar_expert_title = PREMIUM_SIDEBAR_EXPERT_TITLE_BY_CATEGORY.get(
        filter_category, ""
    )

    # 더보기 목록:
    # - 일반 화면: 21번째부터 per_page개(40/80)
    # - 상세검색 결과 화면: 21번째부터 전부 한줄 목록으로 즉시 노출
    try:
        list_per_page = int(request.GET.get('per_page', '40'))
    except (TypeError, ValueError):
        list_per_page = 40
    if list_per_page not in (40, 80):
        list_per_page = 40
    if hide_advanced_filters:
        # 상세검색 결과에서는 카드형 대신 목록형으로 전체 노출
        slice_rest = "0:"
    else:
        # 일반 화면 더보기: 21번째부터 선택 개수(40/80)만 노출
        slice_rest = f"20:{20 + list_per_page}"  # "20:60" or "20:100"

    # 정렬 링크에서 기존 GET 파라미터 유지용 (sort 제외)
    get_copy = request.GET.copy()
    if 'sort' in get_copy:
        get_copy.pop('sort')
    index_query_base = get_copy.urlencode()

    return render(request, 'equipment/index.html', {
        'equipment_list': equipment_list,
        'list_per_page': list_per_page,
        'slice_rest': slice_rest,
        'query': query,
        'sort': sort,
        'total_count': total_count,
        'total_count_label': total_count_label,
        'filter_category': filter_category if filter_category in valid_categories else '',
        'favorited_equipment_ids': favorited_ids,
        'premium_rotation_list': premium_rotation_list,
        'premium_rotation_chunks': premium_rotation_chunks,
        'premium_sidebar_list': premium_sidebar_list,
        'premium_sidebar_slots': premium_sidebar_slots,
        'premium_sidebar_expert_title': premium_sidebar_expert_title,
        'premium_author_ids': premium_author_ids,
        # 상세 검색 상태 유지용
        'filter_maker': maker,
        'filter_sub_type': sub_type,
        'filter_weight_class': weight_class,
        'filter_model': model,
        'filter_year_min': year_min,
        'filter_year_max': year_max,
        'filter_region_sido': region_sido,
        'filter_region_sigungu': region_sigungu,
        'filter_mast_type': mast_type,
        'index_query_base': index_query_base,
        'hide_advanced_filters': hide_advanced_filters,
        'premium_only': premium_only,
    })


def premium_experts_test_view(request):
    """TEST 버튼 전용: 샘플 30개(사진 포함) 미리보기 화면."""
    seeds = list(
        Equipment.objects.visible()
        .filter(equipment_type='excavator')
        .select_related('author')
        .prefetch_related('images')
        .order_by('-created_at')[:30]
    )

    sample_items = []
    if seeds:
        for i in range(30):
            base = seeds[i % len(seeds)]
            first_image = base.images.first()
            sample_items.append({
                'id': i + 1,
                'title': f"[TEST {i + 1:02d}] {base.model_name or '굴삭기 샘플 매물'}",
                'manufacturer': base.manufacturer or '테스트제조사',
                'year': base.year_manufactured or '-',
                'location': base.current_location or base.region_sido or '테스트지역',
                'price': base.listing_price,
                'image_url': first_image.image.url if first_image else '',
                'detail_url': reverse('equipment_detail', args=[base.pk]),
            })
    else:
        for i in range(30):
            sample_items.append({
                'id': i + 1,
                'title': f"[TEST {i + 1:02d}] 굴삭기 샘플 매물",
                'manufacturer': '테스트제조사',
                'year': '-',
                'location': '테스트지역',
                'price': None,
                'image_url': '',
                'detail_url': reverse('index'),
            })

    return render(request, 'equipment/premium_experts_test.html', {
        'sample_items': sample_items,
    })


# [2] 로그인 관련
def user_login(request):
    if request.user.is_authenticated:
        return redirect(request.GET.get('next') or 'index')
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        if not username or not password:
            messages.error(request, '아이디와 비밀번호를 입력하세요.')
            next_url = request.GET.get('next', '')
            from urllib.parse import quote
            _base = '/accounts/{}/login/'
            return render(request, 'registration/login.html', {
                'next_url': next_url,
                'kakao_login_url': _base.format('kakao') + ('?next=' + quote(next_url) if next_url else ''),
                'naver_login_url': _base.format('naver') + ('?next=' + quote(next_url) if next_url else ''),
            })
        user = authenticate(request, username=username, password=password)
        # 보완 로그인은 활성 계정에만 제한한다.
        # (탈퇴 계정은 자동 복구하지 않고 신규가입 흐름으로 유도)
        if user is None:
            # 일부 환경에서 authenticate 실패가 나는 경우를 보완하되,
            # is_active=True 사용자만 허용한다.
            candidate = User.objects.filter(username=username, is_active=True).first()
            if candidate and candidate.check_password(password):
                candidate.backend = 'django.contrib.auth.backends.ModelBackend'
                user = candidate
        if user is not None:
            # 운영 정책: 어드민 계정은 일반 서비스 로그인에서 사용하지 않음
            # (관리자 계정은 /admin/ 에서만 로그인)
            if user.is_staff or user.is_superuser:
                messages.error(request, '관리자 계정은 관리자 페이지에서만 로그인할 수 있습니다.')
                return redirect('/admin/login/')
            login(request, user)
            next_url = request.GET.get('next') or 'index'
            return redirect(next_url)
        messages.error(request, '아이디 또는 비밀번호가 올바르지 않습니다.')
    next_url = request.GET.get('next') or request.POST.get('next', '') or ''
    from urllib.parse import quote
    _base = '/accounts/{}/login/'
    kakao_login_url = _base.format('kakao') + ('?next=' + quote(next_url) if next_url else '')
    naver_login_url = _base.format('naver') + ('?next=' + quote(next_url) if next_url else '')
    return render(request, 'registration/login.html', {
        'next_url': next_url,
        'kakao_login_url': kakao_login_url,
        'naver_login_url': naver_login_url,
    })


def user_logout(request):
    logout(request)
    return redirect('index')


def join_choice(request):
    """회원가입 진입: 휴대폰 입력 → 기존 회원인지 확인 → 기존 전환 또는 신규 가입 안내."""
    if request.user.is_authenticated:
        return redirect('my_page')
    # 회원가입 흐름에서는 이름 매칭 안 함 (legacy 전환 전용 세션 제거)
    if 'legacy_convert_name' in request.session:
        del request.session['legacy_convert_name']
        request.session.modified = True
    from urllib.parse import quote
    _base = '/accounts/{}/login/'
    context = {
        'kakao_signup_url': _base.format('kakao'),
        'naver_signup_url': _base.format('naver'),
    }
    return render(request, 'registration/join_choice.html', context)


def phone_send(request):
    """인증번호 발송. POST phone → 6자리 발송, 재발송 30초 제한. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    phone_raw = (request.POST.get('phone') or '').strip()
    phone_norm = _normalize_phone(phone_raw)
    if not phone_norm or len(phone_norm) < 10:
        return JsonResponse({'ok': False, 'error': '휴대폰 번호를 정확히 입력해 주세요.'})
    from .phone_verify_service import send_code
    success, err = send_code(phone_norm)
    if not success:
        return JsonResponse({'ok': False, 'error': err})
    return JsonResponse({'ok': True})


def legacy_convert_send_code(request):
    """기존 회원 전환: 이름+휴대폰 저장 후 인증번호 발송. POST name, phone. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    name = (request.POST.get('name') or '').strip()
    phone_raw = (request.POST.get('phone') or '').strip()
    phone_norm = _normalize_phone(phone_raw)
    if not phone_norm or len(phone_norm) < 10:
        return JsonResponse({'ok': False, 'error': '휴대폰 번호를 정확히 입력해 주세요.'})
    request.session['legacy_convert_name'] = name or ''
    request.session.modified = True
    from .phone_verify_service import send_code
    success, err = send_code(phone_norm)
    if not success:
        return JsonResponse({'ok': False, 'error': err})
    return JsonResponse({'ok': True})


def phone_verify(request):
    """인증번호 검증. POST phone, code → 성공 시 session['verified_phone'] 설정. 5회 초과 시 실패. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    phone_raw = (request.POST.get('phone') or '').strip()
    code = (request.POST.get('code') or '').strip()
    phone_norm = _normalize_phone(phone_raw)
    if not phone_norm or len(phone_norm) < 10:
        return JsonResponse({'ok': False, 'error': '휴대폰 번호를 입력해 주세요.'})
    if not code or len(code) != 6:
        return JsonResponse({'ok': False, 'error': '인증번호 6자리를 입력해 주세요.'})
    from .phone_verify_service import verify_code
    success, err = verify_code(phone_norm, code)
    if not success:
        return JsonResponse({'ok': False, 'error': err})
    request.session['verified_phone'] = phone_norm  # 하이픈 제거 후 저장
    request.session.modified = True
    return JsonResponse({'ok': True})


def join_check(request):
    """인증 완료된 휴대폰(session)으로 기존 회원 여부 확인. POST 없이 session 기반. JSON.
    session에 legacy_convert_name 있으면 이름(first_name)도 일치할 때만 기존 회원으로 인정."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    phone_norm = request.session.get('verified_phone')
    if not phone_norm:
        return JsonResponse({'ok': False, 'error': '휴대폰 인증을 먼저 완료해 주세요.'})
    import secrets
    legacy_name = (request.session.get('legacy_convert_name') or '').strip()
    profiles = Profile.objects.filter(legacy_member_id__isnull=False).select_related('user')
    profile = None
    for p in profiles:
        if _normalize_phone(p.phone) != phone_norm:
            continue
        if legacy_name:
            fn = (getattr(p.user, 'first_name', None) or '').strip()
            if fn and legacy_name and fn != legacy_name:
                continue
        # 기존회원 전환은 "미전환 legacy 계정"에만 허용:
        # - 아이디가 legacy_로 시작
        # - 활성 계정
        # - 탈퇴 이력 없음
        uname = (getattr(p.user, 'username', None) or '').strip()
        if not uname.startswith('legacy_'):
            continue
        if not getattr(p.user, 'is_active', False):
            continue
        if bool(getattr(p, 'withdrawn_at', None)):
            continue
        profile = p
        break
    if profile is None:
        return JsonResponse({'ok': True, 'found': False})
    user = profile.user

    # 임시 비밀번호는 입력 실수를 줄이기 위해 숫자 4자리로 단순화
    temp_password = "".join(secrets.choice("0123456789") for _ in range(4))
    user.set_password(temp_password)
    user.save(update_fields=['password'])
    # 기존 회원 전환 시 로그인 후 legacy_convert에서 phone_verified 처리
    return JsonResponse({
        'ok': True,
        'found': True,
        'legacy_username': user.username,
        'temp_password': temp_password,
    })


def _normalize_phone(s):
    """숫자만 추출 (010-1234-5678 → 01012345678)."""
    if not s:
        return ''
    import re
    return re.sub(r'\D', '', str(s))


def legacy_convert_intro(request):
    """기존 회원 전환: 이름+휴대폰 → 인증번호 확인 → 기존 정보 조회 → 로그인 후 정식 전환."""
    if request.user.is_authenticated and request.user.username.startswith('legacy_'):
        return redirect('legacy_convert')
    if request.user.is_authenticated:
        return redirect('my_page')
    from urllib.parse import quote
    login_url = '/login/?next=' + quote('/account/convert/')
    return render(request, 'registration/legacy_convert_intro.html', {'login_url': login_url})


def signup_choices(request):
    """신규 회원가입: 카카오/네이버/일반 선택 (필요 시점에만 휴대폰 인증·사업자·유료)."""
    if request.user.is_authenticated:
        return redirect('my_page')
    from urllib.parse import quote
    next_url = request.GET.get('next', '') or ''
    _base = '/accounts/{}/login/'
    kakao_signup_url = _base.format('kakao') + ('?next=' + quote(next_url) if next_url else '')
    naver_signup_url = _base.format('naver') + ('?next=' + quote(next_url) if next_url else '')
    return render(request, 'registration/signup_choices.html', {
        'kakao_signup_url': kakao_signup_url,
        'naver_signup_url': naver_signup_url,
    })


def signup(request):
    if request.method == "POST":
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            verified_phone = request.session.pop('verified_phone', None)
            if verified_phone:
                try:
                    profile = Profile.objects.get(user=user)
                    profile.phone = verified_phone
                    profile.phone_verified = True
                    profile.phone_verified_at = timezone.now()
                    profile.save(update_fields=['phone', 'phone_verified', 'phone_verified_at'])
                except Profile.DoesNotExist:
                    Profile.objects.create(user=user, phone=verified_phone, phone_verified=True, phone_verified_at=timezone.now())
            return redirect("login")
    else:
        form = UserSignupForm()
    return render(request, "registration/signup.html", {"form": form})


def check_username(request):
    from django.http import JsonResponse
    username = (request.GET.get("username") or "").strip()
    if not username:
        return JsonResponse({"ok": False, "msg": "아이디를 입력하세요."})
    existing = User.objects.filter(username=username).first()
    if existing and existing.is_active:
        return JsonResponse({"ok": False, "msg": "이미 사용 중인 아이디입니다."})
    return JsonResponse({"ok": True, "msg": "사용 가능한 아이디입니다."})


def find_username(request):
    """이메일로 가입 시 사용한 아이디(들) 안내"""
    result = None
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        if email:
            users = User.objects.filter(email__iexact=email).values_list('username', flat=True)
            result = list(users) if users else []
        else:
            messages.error(request, '이메일을 입력하세요.')
    return render(request, 'registration/find_username.html', {'result': result})


def my_page(request):
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    if request.method == 'POST' and request.POST.get('action') == 'update_bio':
        if not profile.is_premium_active:
            messages.warning(request, '소개글 설정은 유료회원만 이용할 수 있습니다.')
            return redirect('my_page')
        profile.bio = (request.POST.get('bio') or '').strip()
        profile.save(update_fields=['bio'])
        messages.success(request, '소개글이 저장되었습니다.')
        return redirect('my_page')

    my_equipments = Equipment.objects.filter(author=request.user).order_by('-created_at')
    fav_equipments = Equipment.objects.filter(favorited_by__user=request.user).order_by('-favorited_by__created_at')
    fav_parts = Part.objects.filter(favorited_by__user=request.user).order_by('-favorited_by__created_at')
    total_views = my_equipments.aggregate(total=Coalesce(Sum('view_count'), 0))['total'] or 0
    stats = {
        'my_count': my_equipments.count(),
        'fav_count': fav_equipments.count() + fav_parts.count(),
        'total_views': total_views,
        'grade_label': '유료회원' if profile.is_premium_active else '무료회원',
    }
    is_legacy_user = request.user.username.startswith('legacy_')
    return render(request, 'registration/my_page.html', {
        'profile': profile,
        'my_equipments': my_equipments,
        'fav_equipments': fav_equipments,
        'fav_parts': fav_parts,
        'stats': stats,
        'is_legacy_user': is_legacy_user,
        'free_listing_limit': FREE_LISTING_LIMIT,
    })


@login_required(login_url='/login/')
def billing_upgrade(request):
    """유료 회원 안내 페이지(로그인 필수)."""
    return render(request, 'billing/upgrade.html', {
        'kakao_inquiry_url': getattr(settings, 'KAKAO_INQUIRY_URL', 'https://open.kakao.com/'),
    })


@login_required(login_url='/login/')
def find_my_listings(request):
    """
    기존 매물(작성자 없음 + unclaimed_phone_norm)을 프로필 전화번호로 찾아 계정에 연결.
    소셜 가입자는 본인인증 완료 후 이용.
    """
    if _user_has_social_account(request.user):
        need = _require_phone_verified(request, reverse('find_my_listings'))
        if need:
            return need

    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    norm = normalize_phone_digits(profile.phone)
    if not norm:
        messages.error(
            request,
            '연락처가 등록되어 있어야 합니다. 마이페이지에서 전화번호를 입력한 뒤 휴대폰 본인인증을 완료해 주세요.',
        )
        return redirect('my_page')

    candidates = (
        Equipment.objects.filter(author__isnull=True, unclaimed_phone_norm=norm)
        .order_by('-created_at')
    )

    if request.method == 'POST':
        from django.db import transaction

        raw_ids = request.POST.getlist('equipment_id')
        id_list = []
        for x in raw_ids:
            try:
                id_list.append(int(x))
            except (TypeError, ValueError):
                continue
        if not id_list:
            messages.warning(request, '연결할 매물을 선택해 주세요.')
            return redirect('find_my_listings')

        claimed = 0
        with transaction.atomic():
            for eid in id_list:
                eq = (
                    Equipment.objects.select_for_update()
                    .filter(pk=eid, author__isnull=True, unclaimed_phone_norm=norm)
                    .first()
                )
                if not eq:
                    continue
                eq.author = request.user
                eq.unclaimed_phone_norm = ''
                eq.ownership_claimed_at = timezone.now()
                eq.save(
                    update_fields=['author', 'unclaimed_phone_norm', 'ownership_claimed_at']
                )
                claimed += 1

        if claimed:
            messages.success(request, f'{claimed}건의 매물을 내 계정에 연결했습니다.')
        else:
            messages.warning(request, '연결할 수 있는 매물이 없습니다. 이미 연결되었거나 조건이 맞지 않습니다.')
        return redirect('my_page')

    return render(
        request,
        'registration/find_my_listings.html',
        {
            'candidates': candidates,
            'profile_phone_norm': norm,
        },
    )


@login_required(login_url='/login/')
def verify_phone_page(request):
    """
    휴대폰 본인인증 페이지. 매물 등록·유료 결제 전 필수.
    실제 인증 API(네이버/카카오/나이스 등) 연동 전까지는 안내 페이지.
    DEBUG 시 ?test=1 로 테스트 인증 가능.
    """
    if _get_profile_phone_verified(request.user):
        next_url = request.GET.get('next', '').strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, request.get_host()):
            return redirect(next_url)
        return redirect('my_page')

    if request.method == 'POST':
        phone = (request.POST.get('phone') or '').strip()
        # DEBUG 시 테스트 인증 (실서비스에서는 제거 또는 비활성화)
        next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()
        if getattr(settings, 'DEBUG', False) and request.GET.get('test'):
            try:
                profile = Profile.objects.get(user=request.user)
                profile.phone = phone or profile.phone
                profile.phone_verified = True
                profile.phone_verified_at = timezone.now()
                profile.save()
                messages.success(request, '휴대폰 인증이 완료되었습니다. (테스트 모드)')
                if next_url and url_has_allowed_host_and_scheme(next_url, request.get_host()):
                    return redirect(next_url)
                return redirect('my_page')
            except Profile.DoesNotExist:
                Profile.objects.create(user=request.user, phone=phone or '', phone_verified=True, phone_verified_at=timezone.now())
                messages.success(request, '휴대폰 인증이 완료되었습니다. (테스트 모드)')
                if next_url and url_has_allowed_host_and_scheme(next_url, request.get_host()):
                    return redirect(next_url)
                return redirect('my_page')
        messages.info(request, '본인인증 API 연동 후 이용 가능합니다. 문의: 관리자.')
    next_url = request.GET.get('next', '')
    try:
        profile = Profile.objects.get(user=request.user)
        phone = profile.phone or ''
    except Profile.DoesNotExist:
        phone = ''
    return render(request, 'registration/phone_verify.html', {
        'next_url': next_url,
        'debug': getattr(settings, 'DEBUG', False),
        'phone': phone,
    })


@login_required(login_url='/login/')
def legacy_convert(request):
    """
    이관 회원(legacy_* 아이디) 정식 회원 전환: 새 아이디·이메일·비밀번호 설정.
    회원가입 인증에서 온 경우 session['verified_phone'] → Profile.phone_verified 처리.
    """
    user = request.user
    if not user.username.startswith('legacy_'):
        messages.info(request, '이미 정식 회원이거나 전환 대상이 아닙니다.')
        return redirect('my_page')
    verified_phone = request.session.pop('verified_phone', None)
    if verified_phone:
        try:
            profile = Profile.objects.get(user=user)
            profile.phone = verified_phone  # 하이픈 제거된 번호 저장
            profile.phone_verified = True
            profile.phone_verified_at = timezone.now()
            profile.save(update_fields=['phone', 'phone_verified', 'phone_verified_at'])
        except Profile.DoesNotExist:
            Profile.objects.create(user=user, phone=verified_phone, phone_verified=True, phone_verified_at=timezone.now())

    if request.method == 'POST':
        new_username = (request.POST.get('new_username') or '').strip()
        email = (request.POST.get('email') or '').strip()
        password1 = request.POST.get('password1') or ''
        password2 = request.POST.get('password2') or ''

        errors = []
        if not new_username:
            errors.append('새 로그인 아이디를 입력하세요.')
        elif new_username.startswith('legacy_'):
            errors.append('새 아이디는 legacy_ 로 시작할 수 없습니다.')
        elif User.objects.filter(username=new_username, is_active=True).exclude(pk=user.pk).exists():
            errors.append('이미 사용 중인 아이디입니다.')
        if not email:
            errors.append('이메일을 입력하세요.')
        if len(password1) < 8:
            errors.append('비밀번호는 8자 이상이어야 합니다.')
        elif password1 != password2:
            errors.append('비밀번호가 일치하지 않습니다.')

        if errors:
            for msg in errors:
                messages.error(request, msg)
            return render(request, 'registration/legacy_convert.html', {
                'new_username': new_username,
                'email': email,
            })

        user.username = new_username
        user.email = email
        user.set_password(password1)
        user.save()
        # 비밀번호 변경 후 세션 유지 (Django는 비밀번호 바뀌면 세션 무효화할 수 있음)
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)
        messages.success(request, '정식 회원 전환이 완료되었습니다. 새 아이디로 로그인해 이용해 주세요.')
        return redirect('my_page')

    return render(request, 'registration/legacy_convert.html', {})


@login_required(login_url='/login/')
def account_delete(request):
    """
    회원 탈퇴: 계정 비활성화 + 매물 보관 정책 적용.
    - GET: 확인 페이지
    - POST:
      - 기본: 매물 6개월 보관 후 자동 삭제 예약
      - 옵션 선택 시: 매물 즉시 삭제
    """
    user = request.user

    if request.method != 'POST':
        return render(request, 'registration/account_delete_confirm.html', {'user_obj': user})

    delete_listings_now = request.POST.get('delete_listings_now') == '1'
    now_ts = timezone.now()
    purge_at = now_ts + timedelta(days=180)

    # 매물: 기본은 6개월 보관, 선택 시 즉시 삭제
    if delete_listings_now:
        Equipment.objects.filter(author=user).delete()
    else:
        # author를 유지해야 목록/시세 참고 데이터로 계속 노출됩니다.
        Equipment.objects.filter(author=user).update(is_sold=True)

    # 기타 작성 콘텐츠는 즉시 삭제
    Part.objects.filter(author=user).delete()
    JobPost.objects.filter(author=user).delete()
    SoilPost.objects.filter(author=user).delete()

    username = user.username
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.withdrawn_at = now_ts
    profile.listing_purge_at = None if delete_listings_now else purge_at
    # 정책: 탈퇴 후 재가입은 신규회원가입으로 처리
    # -> legacy_member_id를 비워 기존회원 전환 탐지 대상에서 제외
    profile.legacy_member_id = None
    profile.save(update_fields=['withdrawn_at', 'listing_purge_at', 'legacy_member_id'])

    # 로그인 차단용 비활성화 처리 (데이터 보관 목적)
    user.is_active = False
    user.set_unusable_password()
    user.save(update_fields=['is_active', 'password'])
    logout(request)

    if delete_listings_now:
        messages.success(request, f'"{username}" 계정 탈퇴 및 매물 즉시 삭제가 완료되었습니다.')
    else:
        messages.success(
            request,
            f'"{username}" 계정 탈퇴가 완료되었습니다. 등록 매물은 시세 참고용으로 6개월 보관 후 자동 삭제됩니다.',
        )
    return redirect('index')


def _job_list_equipment_q(equipment_key: str):
    """구인구직 기종 선택 → 제목·내용·필요장비 필드 OR 검색."""
    if not equipment_key:
        return None
    if equipment_key == 'excavator':
        return (
            Q(equipment_type__icontains='굴삭')
            | Q(title__icontains='굴삭')
            | Q(content__icontains='굴삭')
        )
    if equipment_key == 'forklift':
        return (
            Q(equipment_type__icontains='지게')
            | Q(title__icontains='지게차')
            | Q(content__icontains='지게차')
        )
    if equipment_key == 'crane':
        return (
            Q(equipment_type__icontains='크레인')
            | Q(title__icontains='크레인')
            | Q(content__icontains='크레인')
        )
    if equipment_key == 'site':
        return (
            Q(equipment_type__icontains='건설')
            | Q(equipment_type__icontains='현장')
            | Q(title__icontains='건설현장')
            | Q(content__icontains='건설현장')
            | Q(title__icontains='건설')
            | Q(content__icontains='건설')
        )
    if equipment_key == 'etc':
        return (
            Q(equipment_type__icontains='기타')
            | Q(title__icontains='기타')
            | Q(content__icontains='기타')
        )
    return None


JOB_EQUIPMENT_KEYS = frozenset({'excavator', 'forklift', 'crane', 'site', 'etc'})
JOB_EQUIPMENT_LABEL_MAP = {
    'excavator': '굴삭기',
    'forklift': '지게차',
    'crane': '크레인기사',
    'site': '건설현장',
    'etc': '기타',
}
JOB_FORM_EQUIPMENT_CHOICES = [
    ('', '선택 안 함'),
    ('excavator', '굴삭기'),
    ('forklift', '지게차'),
    ('crane', '크레인기사'),
    ('site', '건설현장'),
    ('etc', '기타'),
]


def _merge_job_equipment_type(category_key: str, detail: str) -> str:
    """글쓰기 기종 선택 + 상세 입력 → equipment_type 한 필드에 저장."""
    detail = (detail or '').strip()
    cat = (category_key or '').strip()
    if cat and cat not in JOB_EQUIPMENT_LABEL_MAP:
        cat = ''
    if not cat:
        return detail
    label = JOB_EQUIPMENT_LABEL_MAP[cat]
    if not detail:
        return label
    return f"{label} {detail}"


def _split_job_equipment_type(equipment_type: str) -> tuple:
    """수정 폼: equipment_type → (선택값, 상세 텍스트)."""
    et = (equipment_type or '').strip()
    if not et:
        return '', ''
    for key, label in JOB_EQUIPMENT_LABEL_MAP.items():
        if et.startswith(label):
            rest = et[len(label) :].strip()
            return key, rest
    return '', et


# [3] 구인구직 관련
def job_list(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json

    JOB_EQUIPMENT_CHOICES = [
        ('', '전체'),
        ('excavator', '굴삭기'),
        ('forklift', '지게차'),
        ('crane', '크레인기사'),
        ('site', '건설현장'),
        ('etc', '기타'),
    ]

    qs = JobPost.objects.all().order_by('-created_at')
    job_type = (request.GET.get('type', '') or '').strip().upper()
    region_sido = (request.GET.get('region_sido', '') or '').strip()
    region_sigungu = (request.GET.get('region_sigungu', '') or '').strip()
    equipment = (request.GET.get('equipment', '') or '').strip()
    if equipment not in JOB_EQUIPMENT_KEYS and equipment != '':
        equipment = ''

    if job_type in ('HIRING', 'SEEKING'):
        qs = qs.filter(job_type=job_type)
    if region_sido:
        qs = qs.filter(region_sido=region_sido)
    if region_sigungu:
        qs = qs.filter(region_sigungu=region_sigungu)
    eq_q = _job_list_equipment_q(equipment)
    if eq_q is not None:
        qs = qs.filter(eq_q)

    from django.utils import timezone as dj_tz

    today = dj_tz.now().date()
    job_stats = {
        'total': JobPost.objects.count(),
        'hiring': JobPost.objects.filter(job_type='HIRING').count(),
        'seeking': JobPost.objects.filter(job_type='SEEKING').count(),
        'today': JobPost.objects.filter(created_at__date=today).count(),
    }

    return render(request, 'equipment/job_list.html', {
        'job_list': qs,
        'jobs': qs,
        'filter_type': job_type,
        'filter_region_sido': region_sido,
        'filter_region_sigungu': region_sigungu,
        'filter_equipment': equipment,
        'job_equipment_choices': JOB_EQUIPMENT_CHOICES,
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
        'job_stats': job_stats,
    })


def job_detail(request, pk):
    """구인구직 상세. 문의는 1:1 채팅으로만 가능(공개 댓글 없음)."""
    job = get_object_or_404(JobPost, pk=pk)
    return render(request, 'equipment/job_detail.html', {'job': job})


@login_required(login_url='/login/')
def job_create(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '구인·구직 글 등록을 위해 휴대폰 본인인증이 필요합니다.')
        return redirect_resp
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        writer = (request.POST.get("writer") or "익명").strip()
        contact = (request.POST.get("contact") or "").strip()
        mode = request.POST.get("job_mode", "hire")
        content_main = (request.POST.get("content") or "").strip()
        pay = (request.POST.get("pay") or "").strip()
        exp = (request.POST.get("exp") or "").strip()
        deadline_str = (request.POST.get("deadline") or "").strip()
        region_sido = (request.POST.get("region_sido") or "").strip()
        region_sigungu = (request.POST.get("region_sigungu") or "").strip()
        deadline = None
        if deadline_str:
            from datetime import datetime
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        if mode == "seek":
            location = (request.POST.get("seek_location") or "").strip()
            label = "구직"
            machine = (request.POST.get("seek_machine") or "").strip()
        else:
            location = (request.POST.get("location") or "").strip()
            label = "구인"
            machine = (request.POST.get("machine") or "").strip()

        eq_cat = (request.POST.get("equipment_category") or "").strip()
        if eq_cat not in JOB_EQUIPMENT_KEYS and eq_cat != "":
            eq_cat = ""
        machine = _merge_job_equipment_type(eq_cat, machine)

        deadline_type = (request.POST.get("deadline_type") or "UNTIL_FILLED").strip()
        if deadline_type != "DATE":
            deadline = None
        recruit_count = None
        try:
            rc = request.POST.get("recruit_count", "").strip()
            if rc:
                recruit_count = int(rc)
        except (ValueError, TypeError):
            pass
        doc_resident = "doc_resident" in request.POST
        doc_license = "doc_license" in request.POST
        company_name = (request.POST.get("company_name") or "").strip()
        company_address = (request.POST.get("company_address") or "").strip()

        if not region_sido or not region_sigungu:
            messages.error(request, "시/도와 시/군/구를 모두 선택해 주세요.")
            return render(
                request,
                "equipment/job_form.html",
                {
                    "sido_choices": SIDO_CHOICES,
                    "sigungu_map_json": json.dumps(SIGUNGU_MAP, ensure_ascii=False),
                    "job_equipment_form_choices": JOB_FORM_EQUIPMENT_CHOICES,
                    "equipment_category_selected": eq_cat,
                    "equipment_machine_detail": (
                        (request.POST.get("machine") or request.POST.get("seek_machine") or "").strip()
                    ),
                },
            )
        if not title:
            title = f"[{label}] 제목없음"

        JobPost.objects.create(
            title=title,
            content=content_main,
            location=location,
            region_sido=region_sido,
            region_sigungu=region_sigungu,
            equipment_type=machine,
            pay=pay,
            contact=contact,
            deadline=deadline,
            deadline_type=deadline_type,
            experience=exp,
            writer_display=writer,
            job_type=JobPost.JOB_TYPES[0][0] if mode == "hire" else JobPost.JOB_TYPES[1][0],
            author=request.user if request.user.is_authenticated else None,
            password_hash="",
            recruit_count=recruit_count,
            doc_resident=doc_resident,
            doc_license=doc_license,
            company_name=company_name,
            company_address=company_address,
        )
        return redirect("job_list")

    return render(
        request,
        "equipment/job_form.html",
        {
            "sido_choices": SIDO_CHOICES,
            "sigungu_map_json": json.dumps(SIGUNGU_MAP, ensure_ascii=False),
            "job_equipment_form_choices": JOB_FORM_EQUIPMENT_CHOICES,
            "equipment_category_selected": "",
            "equipment_machine_detail": "",
        },
    )


def job_edit(request, pk):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json
    job = get_object_or_404(JobPost, pk=pk)
    is_author = request.user.is_authenticated and job.author_id == request.user.id
    if not is_author:
        from django.http import Http404
        raise Http404()

    eq_cat, eq_detail = _split_job_equipment_type(job.equipment_type)
    ctx = {
        'job': job,
        'mode': 'edit',
        'is_author': True,
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
        'job_equipment_form_choices': JOB_FORM_EQUIPMENT_CHOICES,
        'equipment_category_selected': eq_cat,
        'equipment_machine_detail': eq_detail,
    }
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        writer = (request.POST.get("writer") or "익명").strip()
        contact = (request.POST.get("contact") or "").strip()
        mode = request.POST.get("job_mode", "hire")
        content_main = (request.POST.get("content") or "").strip()
        pay = (request.POST.get("pay") or "").strip()
        exp = (request.POST.get("exp") or "").strip()
        deadline_str = (request.POST.get("deadline") or "").strip()
        region_sido = (request.POST.get("region_sido") or "").strip()
        region_sigungu = (request.POST.get("region_sigungu") or "").strip()
        deadline = None
        if deadline_str:
            from datetime import datetime
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        if mode == "seek":
            location = (request.POST.get("seek_location") or "").strip()
            label = "구직"
            machine = (request.POST.get("seek_machine") or "").strip()
        else:
            location = (request.POST.get("location") or "").strip()
            label = "구인"
            machine = (request.POST.get("machine") or "").strip()

        eq_cat = (request.POST.get("equipment_category") or "").strip()
        if eq_cat not in JOB_EQUIPMENT_KEYS and eq_cat != "":
            eq_cat = ""
        machine = _merge_job_equipment_type(eq_cat, machine)

        if not region_sido or not region_sigungu:
            messages.error(request, "시/도와 시/군/구를 모두 선택해 주세요.")
            ctx["equipment_category_selected"] = eq_cat
            ctx["equipment_machine_detail"] = (
                (request.POST.get("machine") or request.POST.get("seek_machine") or "").strip()
            )
            return render(request, 'equipment/job_form.html', ctx)

        deadline_type = (request.POST.get("deadline_type") or "UNTIL_FILLED").strip()
        if deadline_type != "DATE":
            deadline = None
        recruit_count = None
        try:
            rc = request.POST.get("recruit_count", "").strip()
            if rc:
                recruit_count = int(rc)
        except (ValueError, TypeError):
            pass
        doc_resident = "doc_resident" in request.POST
        doc_license = "doc_license" in request.POST
        company_name = (request.POST.get("company_name") or "").strip()
        company_address = (request.POST.get("company_address") or "").strip()

        if not title:
            title = f"[{label}] 제목없음"
        job.title = title
        job.content = content_main
        job.location = location
        job.region_sido = region_sido
        job.region_sigungu = region_sigungu
        job.equipment_type = machine
        job.pay = pay
        job.contact = contact
        job.deadline = deadline
        job.deadline_type = deadline_type
        job.experience = exp
        job.writer_display = writer
        job.job_type = JobPost.JOB_TYPES[0][0] if mode == "hire" else JobPost.JOB_TYPES[1][0]
        job.recruit_count = recruit_count
        job.doc_resident = doc_resident
        job.doc_license = doc_license
        job.company_name = company_name
        job.company_address = company_address
        job.save()
        return redirect("job_detail", pk=job.pk)

    return render(request, 'equipment/job_form.html', ctx)


def job_delete(request, pk):
    job = get_object_or_404(JobPost, pk=pk)
    is_author = request.user.is_authenticated and job.author_id == request.user.id
    if not is_author:
        from django.http import Http404
        raise Http404()

    if request.method != "POST":
        return render(request, 'equipment/job_delete_confirm.html', {'job': job, 'is_author': True})
    job.delete()
    messages.success(request, "글이 삭제되었습니다.")
    return redirect('job_list')


# [3-1] 굴삭기 유튜브·정보
def excavator_info(request):
    """유튜브 콘텐츠: 기종 + 목적 동시 필터."""
    from urllib.parse import parse_qs, urlparse

    selected_equipment_type = (request.GET.get("equipment_type", "all") or "all").strip().lower()
    selected_purpose = (request.GET.get("purpose", "all") or "all").strip().lower()

    equipment_tabs = [
        ("all", "전체"),
        ("excavator", "굴삭기"),
        ("forklift", "지게차"),
        ("dump", "덤프트럭"),
        ("loader", "스키로더"),
        ("crane", "크레인"),
        ("attachment", "어태치먼트"),
    ]
    purpose_tabs = [
        ("all", "전체"),
        ("repair", "수리·정비"),
        ("buying", "구매가이드"),
        ("review", "기종리뷰"),
        ("safety", "사고예방"),
    ]
    valid_equipment = {k for k, _ in equipment_tabs}
    valid_purpose = {k for k, _ in purpose_tabs}
    if selected_equipment_type not in valid_equipment:
        selected_equipment_type = "all"
    if selected_purpose not in valid_purpose:
        selected_purpose = "all"

    contents = YoutubeContent.objects.filter(is_active=True)
    if selected_equipment_type != "all":
        contents = contents.filter(equipment_type=selected_equipment_type)
    if selected_purpose != "all":
        contents = contents.filter(purpose=selected_purpose)

    def _to_embed_url(url):
        raw = (url or "").strip()
        if not raw:
            return ""
        try:
            parsed = urlparse(raw)
            host = (parsed.netloc or "").lower()
            if "youtu.be" in host:
                vid = parsed.path.strip("/")
                return f"https://www.youtube.com/embed/{vid}" if vid else ""
            if "youtube.com" in host:
                if parsed.path.startswith("/shorts/"):
                    vid = parsed.path.split("/shorts/", 1)[1].strip("/")
                    return f"https://www.youtube.com/embed/{vid}" if vid else ""
                if parsed.path.startswith("/embed/"):
                    return raw
                vid = parse_qs(parsed.query).get("v", [""])[0].strip()
                return f"https://www.youtube.com/embed/{vid}" if vid else ""
            return raw
        except Exception:
            return raw

    video_items = []
    for item in contents:
        video_items.append({
            "title": item.title,
            "description": item.description,
            "embed_url": _to_embed_url(item.youtube_url),
            "youtube_url": item.youtube_url,
            "equipment_type": item.equipment_type,
            "purpose": item.purpose,
            "equipment_label": item.get_equipment_type_display(),
            "purpose_label": item.get_purpose_display(),
        })

    return render(request, "equipment/excavator_info.html", {
        "equipment_tabs": equipment_tabs,
        "purpose_tabs": purpose_tabs,
        "selected_equipment_type": selected_equipment_type,
        "selected_purpose": selected_purpose,
        "video_items": video_items,
    })


def parts_as(request):
    """부품/AS 센터 지도 + 목록 검색 페이지."""
    region = (request.GET.get('region', '') or '').strip()
    manufacturer = (request.GET.get('manufacturer', '') or '').strip()
    equipment_type = (request.GET.get('equipment_type', '') or '').strip().lower()
    shop_kind = (request.GET.get('shop_kind', '') or '').strip().lower()

    equipment_type_choices = [
        ("all", "전체"),
        ("excavator", "굴삭기"),
        ("forklift", "지게차"),
        ("dump", "덤프트럭"),
        ("loader", "스키로더·로더"),
        ("crane", "크레인"),
        ("attachment", "어태치먼트"),
        ("other", "기타"),
    ]
    equipment_label_by_key = {k: v for k, v in equipment_type_choices if k != "all"}
    equipment_key_by_label = {v: k for k, v in equipment_label_by_key.items()}

    shops_qs = PartsShop.objects.all()
    if region:
        shops_qs = shops_qs.filter(region__icontains=region)
    if manufacturer:
        shops_qs = shops_qs.filter(manufacturer__contains=[manufacturer])
    if shop_kind in ("as", "parts"):
        shops_qs = shops_qs.filter(shop_kind=shop_kind)

    shops_data = []
    for shop in shops_qs:
        equipment_tags = [x for x in (shop.equipment_types or []) if x in equipment_key_by_label]
        equipment_keys = [equipment_key_by_label[x] for x in equipment_tags]
        if equipment_type and equipment_type != "all" and equipment_type not in equipment_keys:
            continue
        shops_data.append({
            "id": shop.pk,
            "name": shop.name,
            "region": shop.region,
            "contact": shop.contact,
            "address": shop.address,
            "note": shop.note,
            "shop_kind": shop.shop_kind,
            "equipment_keys": equipment_keys,
            "equipment_tags": equipment_tags,
            "manufacturers": shop.manufacturer or [],
            "lat": shop.lat,
            "lng": shop.lng,
        })

    region_options = list(
        PartsShop.objects.exclude(region="").values_list("region", flat=True).distinct().order_by("region")
    )
    manufacturer_options = list(PartsShop.MANUFACTURER_CHOICES)
    summary = {
        "total": len(shops_data),
        "as": sum(1 for item in shops_data if item["shop_kind"] == "as"),
        "parts": sum(1 for item in shops_data if item["shop_kind"] == "parts"),
    }

    kakao_map_js_key = (getattr(settings, "KAKAO_MAP_JS_KEY", "") or "").strip()
    if not kakao_map_js_key:
        try:
            from allauth.socialaccount.models import SocialApp
            kakao_map_js_key = (
                SocialApp.objects.filter(provider="kakao")
                .values_list("client_id", flat=True)
                .first()
                or ""
            ).strip()
        except Exception:
            kakao_map_js_key = ""

    return render(request, 'equipment/parts_as.html', {
        'shops': shops_data,
        'region': region,
        'manufacturer': manufacturer,
        'selected_equipment_type': equipment_type or "all",
        'selected_shop_kind': shop_kind or "all",
        'equipment_type_choices': equipment_type_choices,
        'region_options': region_options,
        'manufacturer_options': manufacturer_options,
        'summary': summary,
        'shops_json': json.dumps(shops_data, ensure_ascii=False),
        'kakao_map_js_key': kakao_map_js_key,
    })


# [4] 매물 관련
def equipment_detail(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    if equipment.author_id is None and not (
        request.user.is_authenticated and request.user.is_staff
    ):
        raise Http404()
    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = EquipmentFavorite.objects.filter(user=request.user, equipment=equipment).exists()

    ct = ContentType.objects.get_for_model(Equipment)
    comments = Comment.objects.filter(content_type=ct, object_id=pk).order_by('created_at')

    if request.method == 'POST' and 'comment_content' in request.POST:
        content = (request.POST.get('comment_content') or '').strip()
        if content:
            Comment.objects.create(
                author=request.user if request.user.is_authenticated else None,
                author_name=(request.POST.get('comment_author_name') or '').strip() or '익명',
                content=content,
                content_type=ct,
                object_id=pk,
            )
        return redirect('equipment_detail', pk=pk)

    if request.method == 'GET':
        Equipment.objects.filter(pk=equipment.pk).update(view_count=F('view_count') + 1)
        equipment.refresh_from_db(fields=['view_count'])

    author_phone = None
    author_is_dealer = False
    author_is_premium = False
    author_display = None
    author_company = ""
    author_youtube = ""
    if equipment.author:
        try:
            profile = getattr(equipment.author, 'profile', None)
            if profile:
                author_phone = getattr(profile, 'phone', None)
                if author_phone is not None:
                    author_phone = str(author_phone).strip()
                    # 전화번호는 숫자가 있어야 유효 (예: legacy_XXXX 같은 값 방지)
                    if author_phone and not any(ch.isdigit() for ch in author_phone):
                        author_phone = None
                author_is_dealer = getattr(profile, 'user_type', None) == 'DEALER'
                author_is_premium = getattr(profile, 'is_premium_active', False) or (
                    equipment.author_id in set(get_premium_user_ids())
                )
                author_display = getattr(profile, 'company_name', None) or equipment.author.get_full_name() or equipment.author.username
                author_company = (getattr(profile, "company_name", None) or "").strip()
                author_youtube = (getattr(profile, "youtube_url", None) or "").strip()
            else:
                author_display = equipment.author.get_full_name() or equipment.author.username
                author_is_premium = equipment.author_id in set(get_premium_user_ids())
        except Exception:
            author_display = equipment.author.username if equipment.author else None

    # 작성자 연결이 없는 이관 매물 보정:
    # 같은 핵심 정보(모델/가격/위치/등록일)의 최근 매물에서 연락처를 fallback으로 사용
    if not author_phone:
        sibling_qs = (
            Equipment.objects.select_related('author__profile')
            .exclude(pk=equipment.pk)
            .exclude(author__isnull=True)
            .filter(
                model_name=equipment.model_name,
                listing_price=equipment.listing_price,
                current_location=equipment.current_location,
                created_at__date=equipment.created_at.date(),
            )
            .order_by('-created_at')
        )
        for sibling in sibling_qs[:10]:
            sibling_profile = getattr(getattr(sibling, 'author', None), 'profile', None)
            sibling_phone = getattr(sibling_profile, 'phone', None) if sibling_profile else None
            if sibling_phone:
                author_phone = str(sibling_phone).strip()
                if author_phone and not any(ch.isdigit() for ch in author_phone):
                    author_phone = None
                if not author_phone:
                    continue
                if not author_display:
                    author_display = (
                        getattr(sibling_profile, 'company_name', None)
                        or sibling.author.get_full_name()
                        or sibling.author.username
                    )
                if not author_is_dealer:
                    author_is_dealer = getattr(sibling_profile, 'user_type', None) == 'DEALER'
                if not author_is_premium:
                    author_is_premium = (
                        getattr(sibling_profile, 'is_premium_active', False)
                        or sibling.author_id in set(get_premium_user_ids())
                    )
                break

    # 실제 파일이 존재하는 사진만 상세 화면에 노출 (깨진 이미지 방지)
    detail_images = []
    for image in equipment.images.all():
        try:
            image_name = getattr(image.image, 'name', '') or ''
            if image_name and image.image.storage.exists(image_name):
                detail_images.append(image)
        except Exception:
            continue

    # 금융 예상 한도 / 월 납입액(60개월, 연 7% 가정)
    finance_limit = None
    finance_monthly_60 = None
    try:
        if equipment.listing_price and equipment.listing_price > 0:
            price = Decimal(equipment.listing_price)
            principal = (price * Decimal('0.8')).quantize(Decimal('1.'), rounding=ROUND_HALF_UP)  # 매물가의 80% (만원 단위)
            r = Decimal('0.07') / Decimal('12')  # 연 7% 가정
            n = Decimal('60')
            if r > 0:
                factor = (r * (1 + r) ** n) / ((1 + r) ** n - 1)
                monthly = (principal * factor).quantize(Decimal('1.'), rounding=ROUND_HALF_UP)
            else:
                monthly = (principal / n).quantize(Decimal('1.'), rounding=ROUND_HALF_UP)
            finance_limit = principal
            finance_monthly_60 = monthly
    except Exception:
        finance_limit = None
        finance_monthly_60 = None

    # 비슷한 기종·년식(±2년) 시세 통계 및 비슷한 매물 목록 (노출 중인 것만)
    similar_qs = Equipment.objects.visible().exclude(pk=equipment.pk).filter(is_sold=False)
    year_val = equipment.year_manufactured or 0
    if equipment.manufacturer:
        similar_qs = similar_qs.filter(manufacturer=equipment.manufacturer)
    if year_val and 1980 <= year_val <= 2030:
        similar_qs = similar_qs.filter(
            year_manufactured__gte=year_val - 2,
            year_manufactured__lte=year_val + 2,
        )
    similar_stats = similar_qs.aggregate(
        cnt=Count('id'),
        price_min=Min('listing_price'),
        price_max=Max('listing_price'),
        price_avg=Avg('listing_price'),
    )
    similar_list = list(similar_qs.order_by('-created_at')[:6])

    # 상세 좌측 레일(굴삭기 전용): 어태치먼트/타이어 전문가 카드
    left_specialist_cards = []
    if (equipment.equipment_type or "") == "excavator":
        left_specialist_cards = list(
            Equipment.objects.visible()
            .filter(is_sold=False)
            .filter(
                Q(equipment_type="attachment")
                | Q(equipment_type="excavator", sub_type="EXC_TIRE")
            )
            .exclude(pk=equipment.pk)
            .select_related("author__profile")
            .order_by("?")[:5]
        )

    # 상세 레일·연동: 같은 기종 유료 전문가 (현재 매물 제외). 굴삭기는 좌우 10+10 슬롯용으로 20칸 패딩
    _ptype = equipment.equipment_type or None
    _raw_sidebar = get_premium_equipment_sidebar(
        limit=max(24, PREMIUM_SIDEBAR_INDEX_TOTAL + 4), equipment_type=_ptype
    )
    filtered_sidebar = [eq for eq in _raw_sidebar if eq.pk != equipment.pk]
    premium_sidebar_list = filtered_sidebar[:8]
    premium_sidebar_expert_title = PREMIUM_SIDEBAR_EXPERT_TITLE_BY_CATEGORY.get(_ptype or "", "")
    if not premium_sidebar_expert_title and _ptype:
        premium_sidebar_expert_title = (
            f"{equipment.get_equipment_type_display()} 전문가들"
        )
    if _ptype == "excavator":
        premium_sidebar_slots = pad_premium_sidebar_slots(
            filtered_sidebar[:PREMIUM_SIDEBAR_INDEX_TOTAL],
            PREMIUM_SIDEBAR_INDEX_TOTAL,
        )
    else:
        premium_sidebar_slots = []

    # 이 판매자의 다른 매물 6개 미리보기 (본문 제외)
    author_other_listings = []
    if equipment.author_id:
        author_other_listings = list(
            Equipment.objects.visible()
            .filter(author_id=equipment.author_id, is_sold=False)
            .exclude(pk=equipment.pk)
            .order_by('-created_at')[:6]
        )

    # 우측 레일: 전국 부품점 A/S 센터(지도 이동 링크용)
    shops_qs = PartsShop.objects.all().order_by('region', 'name')
    nearby_parts_shops = []
    if equipment.region_sido:
        nearby_parts_shops = list(shops_qs.filter(region__icontains=equipment.region_sido)[:6])
    if not nearby_parts_shops:
        nearby_parts_shops = list(shops_qs[:6])

    # 끌어올리기: 본인 매물 + 유료회원 + 주 1회 제한
    can_bump = False
    next_bump_at = None
    if request.user.is_authenticated and equipment.author_id == request.user.id and author_is_premium:
        from datetime import timedelta
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        if not equipment.last_bumped_at or equipment.last_bumped_at <= week_ago:
            can_bump = True
        else:
            next_bump_at = equipment.last_bumped_at + timedelta(days=7)

    return render(request, 'equipment/equipment_detail.html', {
        'equipment': equipment,
        'detail_images': detail_images,
        'is_favorited': is_favorited,
        'comments': comments,
        'author_phone': author_phone,
        'author_is_dealer': author_is_dealer,
        'author_is_premium': author_is_premium,
        'author_display': author_display,
        'author_company': author_company,
        'author_youtube': author_youtube,
        'similar_stats': similar_stats,
        'similar_list': similar_list,
        'finance_limit': finance_limit,
        'finance_monthly_60': finance_monthly_60,
        'left_specialist_cards': left_specialist_cards,
        'premium_sidebar_list': premium_sidebar_list,
        'premium_sidebar_slots': premium_sidebar_slots,
        'premium_sidebar_expert_title': premium_sidebar_expert_title,
        'author_other_listings': author_other_listings,
        'nearby_parts_shops': nearby_parts_shops,
        'can_bump': can_bump,
        'next_bump_at': next_bump_at,
    })


def equipment_create(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json

    if not request.user.is_authenticated:
        return redirect('login')
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '매물 등록을 위해 휴대폰 본인인증이 필요합니다.')
        return redirect_resp

    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            # 무료 회원: 10건 초과 시 등록 불가 (유료 전환 유도)
            if not is_user_premium(request.user):
                current_count = get_free_listing_count(request.user)
                if current_count >= FREE_LISTING_LIMIT:
                    messages.error(
                        request,
                        f'무료 회원은 한 달에 매물을 {FREE_LISTING_LIMIT}건까지만 등록할 수 있습니다. '
                        '이번 달 한도를 모두 사용했습니다. 삭제 후 다시 올려도 당월 건수에 포함되며, 다음 달부터 새로 등록할 수 있습니다.'
                    )
                    return render(request, 'equipment/equipment_form.html', {
                        'form': form,
                        'mode': 'create',
                        'sido_choices': SIDO_CHOICES,
                        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
                        'free_listing_count': current_count,
                        'free_listing_limit': FREE_LISTING_LIMIT,
                        'is_premium': False,
                    })
            # 허위 매물 방지: 사진 최소 1장 필수
            image_files = request.FILES.getlist('images')
            if not image_files or len(image_files) < 1:
                form.add_error(None, ValidationError('허위 매물 방지를 위해 사진을 최소 1장 이상 등록해주세요.'))
            else:
                # 무료회원 재등록 제한: 동일 모델/동일 사진 30일 이내 재업로드 차단
                if not is_user_premium(request.user):
                    model_name = (form.cleaned_data.get('model_name') or '').strip()
                    first_hash = _image_hash_from_upload(image_files[0])
                    from datetime import timedelta
                    since = timezone.now() - timedelta(days=30)
                    if DeletedListingLog.objects.filter(
                        user=request.user,
                        deleted_at__gte=since,
                    ).filter(
                        Q(model_name=model_name) | (Q(image_hash=first_hash) if first_hash else Q(pk=-1))
                    ).exists():
                        messages.error(
                            request,
                            '동일한 매물(같은 모델·같은 사진)은 삭제 후 30일이 지나야 다시 등록할 수 있습니다. '
                            '유료 회원은 끌어올리기로 상단 노출을 이용해 주세요.'
                        )
                        return render(request, 'equipment/equipment_form.html', {
                            'form': form,
                            'mode': 'create',
                            'sido_choices': SIDO_CHOICES,
                            'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
                            'free_listing_count': get_free_listing_count(request.user),
                            'free_listing_limit': FREE_LISTING_LIMIT,
                            'is_premium': False,
                        })
                # 해시 계산으로 읽은 첫 이미지 포인터 초기화 (저장 시 사용)
                image_files[0].seek(0)
                obj = form.save(commit=False)
                obj.author = request.user
                obj.current_location = _build_location_text(obj.region_sido, obj.region_sigungu)
                obj.save()
                for f in image_files:
                    EquipmentImage.objects.create(equipment=obj, image=f)
                return redirect('equipment_detail', obj.pk)
    else:
        form = EquipmentForm(initial={'equipment_type': 'excavator'})

    free_count = get_free_listing_count(request.user) if request.user.is_authenticated else 0
    return render(request, 'equipment/equipment_form.html', {
        'form': form,
        'mode': 'create',
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
        'free_listing_count': free_count,
        'free_listing_limit': FREE_LISTING_LIMIT,
        'is_premium': is_user_premium(request.user),
    })


def equipment_edit(request, pk):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json

    obj = get_object_or_404(Equipment, pk=pk)

    if not request.user.is_authenticated:
        return redirect('login')

    # 내 글만 수정 가능 (author가 None이면 일단 막음)
    if obj.author_id != request.user.id:
        return redirect('equipment_detail', obj.pk)

    if request.method == 'POST':
        form = EquipmentEditForm(request.POST, instance=obj)
        if form.is_valid():
            image_files = request.FILES.getlist('images')
            has_existing = obj.images.exists()
            if not has_existing and (not image_files or len(image_files) < 1):
                form.add_error(None, ValidationError('허위 매물 방지를 위해 사진을 최소 1장 이상 등록해주세요.'))
            else:
                obj = form.save(commit=False)
                obj.current_location = _build_location_text(obj.region_sido, obj.region_sigungu)
                obj.save()
                for f in image_files:
                    EquipmentImage.objects.create(equipment=obj, image=f)
                return redirect('equipment_detail', obj.pk)
    else:
        form = EquipmentEditForm(instance=obj)

    return render(request, 'equipment/equipment_form.html', {
        'form': form,
        'mode': 'edit',
        'equipment': obj,
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
    })


def equipment_delete(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    if not request.user.is_authenticated:
        return redirect('login')
    if equipment.author_id != request.user.id:
        messages.error(request, '본인만 삭제할 수 있습니다.')
        return redirect('equipment_detail', pk=pk)
    if request.method != 'POST':
        next_url = request.GET.get('next', '')
        return render(request, 'equipment/equipment_delete_confirm.html', {'equipment': equipment, 'next_url': next_url})
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if next_url and url_has_allowed_host_and_scheme(next_url):
        redirect_to = next_url
    else:
        redirect_to = reverse('my_page')
    # 무료회원 삭제 시 재등록 제한용 로그 (동일 사진/모델 재업로드 감지)
    if not is_user_premium(request.user):
        try:
            img_hash = _image_hash_from_equipment(equipment)
            DeletedListingLog.objects.create(
                user=request.user,
                model_name=(equipment.model_name or '').strip(),
                image_hash=img_hash or '',
            )
        except Exception:
            pass
    equipment.delete()
    messages.success(request, '매물이 삭제되었습니다.')
    return redirect(redirect_to)


def equipment_bump(request, pk):
    """끌어올리기 — 유료회원만 주 1회. 매물을 목록 상단(최신순)으로 올림."""
    equipment = get_object_or_404(Equipment, pk=pk)
    if not request.user.is_authenticated:
        messages.info(request, '로그인 후 이용해 주세요.')
        return redirect('login')
    if equipment.author_id != request.user.id:
        messages.error(request, '본인 매물만 끌어올릴 수 있습니다.')
        return redirect('equipment_detail', pk=pk)
    if not is_user_premium(request.user):
        messages.error(request, '끌어올리기는 유료 회원만 이용할 수 있습니다.')
        return redirect('equipment_detail', pk=pk)
    now = timezone.now()
    from datetime import timedelta
    week_ago = now - timedelta(days=7)
    if equipment.last_bumped_at and equipment.last_bumped_at > week_ago:
        next_at = equipment.last_bumped_at + timedelta(days=7)
        messages.warning(
            request,
            f'끌어올리기는 주 1회만 가능합니다. 다음 이용 가능: {next_at.strftime("%Y-%m-%d %H:%M")}'
        )
        return redirect('equipment_detail', pk=pk)
    equipment.last_bumped_at = now
    equipment.save(update_fields=['last_bumped_at'])
    messages.success(request, '끌어올리기가 완료되었습니다. 최신순 목록 상단에 노출됩니다.')
    return redirect('equipment_detail', pk=pk)


def toggle_equipment_favorite(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')
    equipment = get_object_or_404(Equipment, pk=pk)
    fav, created = EquipmentFavorite.objects.get_or_create(user=request.user, equipment=equipment)
    if not created:
        fav.delete()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'index'
    return redirect(next_url)


def author_listings(request, user_id):
    """이 회원이 올린 모든 매물 보기."""
    author_user = get_object_or_404(User, pk=user_id)
    author_profile = getattr(author_user, 'profile', None)
    author_showcase_public = bool(
        author_profile and getattr(author_profile, 'is_premium_active', False)
    )
    # "이 회원 매물 전체 보기"는 유료 회원만 공개
    if not author_showcase_public:
        raise Http404()

    base_qs = (
        Equipment.objects.visible()
        .filter(author_id=user_id)
        .select_related('author')
        .prefetch_related('images')
    )
    cat = (request.GET.get('category') or '').strip().lower()
    valid_cats = {c[0] for c in Equipment._meta.get_field('equipment_type').choices}
    if cat in valid_cats:
        base_qs = base_qs.filter(equipment_type=cat)

    sort = (request.GET.get('sort') or 'latest').strip().lower()
    if sort == 'price_low':
        qs = base_qs.order_by('listing_price', '-created_at')
    elif sort == 'price_high':
        qs = base_qs.order_by('-listing_price', '-created_at')
    else:
        sort = 'latest'
        qs = base_qs.order_by('-created_at')

    listings = list(qs)
    featured_listings = list(base_qs.order_by('-created_at')[:3])
    total_count = len(listings)
    sold_count = sum(1 for item in listings if item.is_sold)
    trust_score = 5 if (author_profile and author_profile.is_premium_active) else 4
    avg_response_text = "빠름"
    favorited_ids = set()
    if request.user.is_authenticated:
        favorited_ids = set(
            EquipmentFavorite.objects.filter(user=request.user).values_list(
                'equipment_id', flat=True
            )
        )
    premium_author_ids = set(get_premium_user_ids())

    return render(request, 'equipment/author_listings.html', {
        'author_user': author_user,
        'author_profile': author_profile,
        'author_showcase_public': author_showcase_public,
        'listings': listings,
        'favorited_equipment_ids': favorited_ids,
        'premium_author_ids': premium_author_ids,
        'filter_category_param': cat if cat in valid_cats else '',
        'featured_listings': featured_listings,
        'sort_param': sort,
        'total_count': total_count,
        'sold_count': sold_count,
        'trust_score': trust_score,
        'avg_response_text': avg_response_text,
    })


# [5] 부품 관련
def part_list(request):
    part_list_qs = Part.objects.all()
    category = (request.GET.get('category') or '').strip().upper()
    if category and category in dict(Part.PART_CATEGORIES):
        part_list_qs = part_list_qs.filter(category=category)
    favorited_part_ids = set()
    if request.user.is_authenticated:
        favorited_part_ids = set(PartFavorite.objects.filter(user=request.user).values_list('part_id', flat=True))
    return render(request, 'equipment/part_list.html', {
        'part_list': part_list_qs,
        'favorited_part_ids': favorited_part_ids,
        'filter_category': category,
    })


def part_detail(request, pk):
    part = get_object_or_404(Part, pk=pk)
    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = PartFavorite.objects.filter(user=request.user, part=part).exists()

    ct = ContentType.objects.get_for_model(Part)
    comments = Comment.objects.filter(content_type=ct, object_id=pk).order_by('created_at')

    if request.method == 'POST' and 'comment_content' in request.POST:
        content = (request.POST.get('comment_content') or '').strip()
        if content:
            Comment.objects.create(
                author=request.user if request.user.is_authenticated else None,
                author_name=(request.POST.get('comment_author_name') or '').strip() or '익명',
                content=content,
                content_type=ct,
                object_id=pk,
            )
        return redirect('part_detail', pk=pk)

    return render(request, 'equipment/part_detail.html', {
        'part': part,
        'is_favorited': is_favorited,
        'comments': comments,
    })


def toggle_part_favorite(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')
    part = get_object_or_404(Part, pk=pk)
    fav, created = PartFavorite.objects.get_or_create(user=request.user, part=part)
    if not created:
        fav.delete()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'part_list'
    return redirect(next_url)


def part_create(request):
    if not request.user.is_authenticated:
        return redirect('login')
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '부품 매물 등록을 위해 휴대폰 본인인증이 필요합니다.')
        return redirect_resp

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        price = (request.POST.get("price") or "").strip()
        location = (request.POST.get("location") or "").strip()
        category = (request.POST.get("category") or "ETC").strip()
        compatibility = (request.POST.get("compatibility") or "").strip()
        description = (request.POST.get("description") or "").strip()
        contact = (request.POST.get("contact") or "").strip()

        part = Part.objects.create(
            title=title,
            price=price,
            location=location,
            category=category,
            compatibility=compatibility,
            description=description,
            contact=contact,
            author=request.user,
        )

        # ✅ 사진 여러장 저장
        for f in request.FILES.getlist("images"):
            PartImage.objects.create(part=part, image=f)

        return redirect("part_detail", part.pk)

    return render(request, "equipment/part_form.html", {"mode": "create"})


def part_edit(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    part = get_object_or_404(Part, pk=pk)

    # 내 글만 수정 가능
    if part.author_id != request.user.id:
        return redirect("part_detail", part.pk)

    if request.method == "POST":
        part.title = (request.POST.get("title") or "").strip()
        part.price = (request.POST.get("price") or "").strip()
        part.location = (request.POST.get("location") or "").strip()
        part.category = (request.POST.get("category") or "ETC").strip()
        part.compatibility = (request.POST.get("compatibility") or "").strip()
        part.description = (request.POST.get("description") or "").strip()
        part.contact = (request.POST.get("contact") or "").strip()
        part.save()

        # ✅ 수정 시 새 사진 추가 업로드(기존 사진 유지)
        for f in request.FILES.getlist("images"):
            PartImage.objects.create(part=part, image=f)

        return redirect("part_detail", part.pk)

    return render(request, "equipment/part_form.html", {"mode": "edit", "part": part})


def part_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    part = get_object_or_404(Part, pk=pk)
    if part.author_id != request.user.id:
        return redirect("part_detail", part.pk)

    part.delete()
    return redirect("part_list")
