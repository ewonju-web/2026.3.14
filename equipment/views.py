from equipment.forms import UserSignupForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q, Min, Max, Avg, Count
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from .models import Equipment, JobPost, Part, EquipmentImage, PartImage, PartsShop, EquipmentFavorite, PartFavorite, Comment
from .forms import EquipmentForm, EquipmentEditForm


# [1] 메인 페이지 (키워드 + 정렬만)
def index(request):
    query = (request.GET.get('q', '') or '').strip()
    sort = request.GET.get('sort', 'new')
    filter_category = (request.GET.get('category', '') or '').strip().lower()  # excavator, forklift, dump, loader, etc

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

    # 목록/검색: NORMAL만 노출(EXPIRED_HIDDEN 제외). 상세 직접 URL은 별도 허용.
    equipment_list = Equipment.objects.visible()
    valid_categories = ('excavator', 'forklift', 'dump', 'loader', 'attachment', 'etc')
    if filter_category in valid_categories:
        equipment_list = equipment_list.filter(equipment_type=filter_category)

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
            equipment_list = equipment_list.filter(sub_type=sub_type)
        if weight_class:
            equipment_list = equipment_list.filter(weight_class=weight_class)
    elif filter_category == 'forklift':
        if sub_type:
            equipment_list = equipment_list.filter(sub_type=sub_type)
        if weight_class:
            equipment_list = equipment_list.filter(weight_class=weight_class)
        if mast_type:
            equipment_list = equipment_list.filter(mast_type=mast_type)

    if sort == 'price_asc':
        equipment_list = equipment_list.order_by('listing_price')
    elif sort == 'price_desc':
        equipment_list = equipment_list.order_by('-listing_price')
    else:
        equipment_list = equipment_list.order_by('-created_at')

    favorited_ids = set()
    if request.user.is_authenticated:
        favorited_ids = set(EquipmentFavorite.objects.filter(user=request.user).values_list('equipment_id', flat=True))

    # 더보기 목록: 21번째부터 per_page개 (40 또는 80)
    try:
        list_per_page = int(request.GET.get('per_page', '40'))
    except (TypeError, ValueError):
        list_per_page = 40
    if list_per_page not in (40, 80):
        list_per_page = 40
    slice_rest = f"20:{20 + list_per_page}"  # "20:60" or "20:100"

    return render(request, 'equipment/equipment_list.html', {
        'equipment_list': equipment_list,
        'list_per_page': list_per_page,
        'slice_rest': slice_rest,
        'query': query,
        'sort': sort,
        'filter_category': filter_category if filter_category in ('excavator', 'forklift', 'dump', 'loader', 'attachment', 'etc') else '',
        'favorited_equipment_ids': favorited_ids,
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
            return render(request, 'registration/login.html')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next') or 'index'
            return redirect(next_url)
        messages.error(request, '아이디 또는 비밀번호가 올바르지 않습니다.')
    return render(request, 'registration/login.html')


def user_logout(request):
    logout(request)
    return redirect('index')


def signup(request):
    if request.method == "POST":
        form = UserSignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = UserSignupForm()
    return render(request, "registration/signup.html", {"form": form})


def check_username(request):
    from django.http import JsonResponse
    username = (request.GET.get("username") or "").strip()
    if not username:
        return JsonResponse({"ok": False, "msg": "아이디를 입력하세요."})
    if User.objects.filter(username=username).exists():
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

    my_equipments = Equipment.objects.filter(author=request.user).order_by('-created_at')
    fav_equipments = Equipment.objects.filter(favorited_by__user=request.user).order_by('-favorited_by__created_at')
    fav_parts = Part.objects.filter(favorited_by__user=request.user).order_by('-favorited_by__created_at')
    return render(request, 'registration/my_page.html', {
        'my_equipments': my_equipments,
        'fav_equipments': fav_equipments,
        'fav_parts': fav_parts,
    })


# [3] 구인구직 관련
def job_list(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json
    qs = JobPost.objects.all().order_by('-created_at')
    job_type = (request.GET.get('type', '') or '').strip().upper()
    search = (request.GET.get('q', '') or '').strip()
    region_sido = (request.GET.get('region_sido', '') or '').strip()
    region_sigungu = (request.GET.get('region_sigungu', '') or '').strip()

    if job_type in ('HIRING', 'SEEKING'):
        qs = qs.filter(job_type=job_type)
    if search:
        qs = qs.filter(
            Q(location__icontains=search)
            | Q(title__icontains=search)
            | Q(content__icontains=search)
            | Q(writer_display__icontains=search)
            | Q(region_sido__icontains=search)
            | Q(region_sigungu__icontains=search)
        )
    if region_sido:
        qs = qs.filter(region_sido=region_sido)
    if region_sigungu:
        qs = qs.filter(region_sigungu=region_sigungu)

    return render(request, 'equipment/job_list.html', {
        'job_list': qs,
        'jobs': qs,
        'filter_type': job_type,
        'filter_query': search,
        'filter_region_sido': region_sido,
        'filter_region_sigungu': region_sigungu,
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
    })


def job_detail(request, pk):
    """구인구직 상세. 문의는 1:1 채팅으로만 가능(공개 댓글 없음)."""
    job = get_object_or_404(JobPost, pk=pk)
    return render(request, 'equipment/job_detail.html', {'job': job})


@login_required(login_url='/login/')
def job_create(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json
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
            return render(request, "equipment/job_form.html", {
                'sido_choices': SIDO_CHOICES,
                'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
            })
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

    return render(request, "equipment/job_form.html", {
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
    })


def job_edit(request, pk):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json
    job = get_object_or_404(JobPost, pk=pk)
    is_author = request.user.is_authenticated and job.author_id == request.user.id
    if not is_author:
        from django.http import Http404
        raise Http404()

    ctx = {
        'job': job,
        'mode': 'edit',
        'is_author': True,
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
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
        if not region_sido or not region_sigungu:
            messages.error(request, "시/도와 시/군/구를 모두 선택해 주세요.")
            return render(request, 'equipment/job_form.html', ctx)
        if mode == "seek":
            location = (request.POST.get("seek_location") or "").strip()
            label = "구직"
            machine = (request.POST.get("seek_machine") or "").strip()
        else:
            location = (request.POST.get("location") or "").strip()
            label = "구인"
            machine = (request.POST.get("machine") or "").strip()

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
    """고장수리, 공사, 일머리, 부분별 등 굴삭기 관련 유튜브 링크/재생목록. playlist_id는 추후 .env 또는 DB에서 변경 가능."""
    import os
    default_playlist = os.getenv('YOUTUBE_DEFAULT_PLAYLIST_ID', 'PLm278VnZ6B9Z4Hsc62wR3r-3L0H1S9n-x')
    categories = [
        {'title': '고장·수리', 'description': '굴삭기 고장 진단, 수리, 점검 영상', 'playlist_id': os.getenv('YOUTUBE_PLAYLIST_REPAIR', default_playlist)},
        {'title': '공사·현장', 'description': '굴삭기 공사, 현장 작업, 작업 요령', 'playlist_id': os.getenv('YOUTUBE_PLAYLIST_WORK', default_playlist)},
        {'title': '일머리·운전', 'description': '굴삭기 운전 요령, 일머리, 안전', 'playlist_id': os.getenv('YOUTUBE_PLAYLIST_OPERATE', default_playlist)},
        {'title': '부분별·부품', 'description': '부품별 설명, 점검, 교체', 'playlist_id': os.getenv('YOUTUBE_PLAYLIST_PARTS', default_playlist)},
        {'title': '굴삭기나라 TV', 'description': '굴삭기 관련 다양한 정보', 'playlist_id': default_playlist},
    ]
    return render(request, 'equipment/excavator_info.html', {'categories': categories})


def parts_as(request):
    """부품/AS: 전국 굴삭기 부품점 연락처 검색 + 어태치먼트 종류별 광고 영역"""
    region = (request.GET.get('region', '') or '').strip()
    query = (request.GET.get('q', '') or '').strip()
    shops = PartsShop.objects.all()
    if region:
        shops = shops.filter(region__icontains=region)
    if query:
        shops = shops.filter(
            Q(name__icontains=query) | Q(address__icontains=query) | Q(note__icontains=query)
        )
    attachment_categories = Part.PART_CATEGORIES  # 어태치먼트 종류별 광고 슬롯용
    return render(request, 'equipment/parts_as.html', {
        'shops': shops,
        'region': region,
        'query': query,
        'attachment_categories': attachment_categories,
    })


# [4] 매물 관련
def equipment_detail(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
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

    author_phone = None
    author_is_dealer = False
    author_display = None
    if equipment.author:
        try:
            profile = getattr(equipment.author, 'profile', None)
            if profile:
                author_phone = getattr(profile, 'phone', None)
                author_is_dealer = getattr(profile, 'user_type', None) == 'DEALER'
                author_display = getattr(profile, 'company_name', None) or equipment.author.get_full_name() or equipment.author.username
            else:
                author_display = equipment.author.get_full_name() or equipment.author.username
        except Exception:
            author_display = equipment.author.username if equipment.author else None

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

    return render(request, 'equipment/equipment_detail.html', {
        'equipment': equipment,
        'is_favorited': is_favorited,
        'comments': comments,
        'author_phone': author_phone,
        'author_is_dealer': author_is_dealer,
        'author_display': author_display,
        'similar_stats': similar_stats,
        'similar_list': similar_list,
        'finance_limit': finance_limit,
        'finance_monthly_60': finance_monthly_60,
    })


def equipment_create(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            # 허위 매물 방지: 사진 최소 1장 필수
            image_files = request.FILES.getlist('images')
            if not image_files or len(image_files) < 1:
                form.add_error(None, ValidationError('허위 매물 방지를 위해 사진을 최소 1장 이상 등록해주세요.'))
            else:
                obj = form.save(commit=False)
                obj.author = request.user
                obj.save()
                for f in image_files:
                    EquipmentImage.objects.create(equipment=obj, image=f)
                return redirect('equipment_detail', obj.pk)
    else:
        form = EquipmentForm(initial={'equipment_type': 'excavator'})

    return render(request, 'equipment/equipment_form.html', {'form': form, 'mode': 'create'})


def equipment_edit(request, pk):
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
                form.save()
                for f in image_files:
                    EquipmentImage.objects.create(equipment=obj, image=f)
                return redirect('equipment_detail', obj.pk)
    else:
        form = EquipmentEditForm(instance=obj)

    return render(request, 'equipment/equipment_form.html', {'form': form, 'mode': 'edit', 'equipment': obj})


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
    equipment.delete()
    messages.success(request, '매물이 삭제되었습니다.')
    return redirect(redirect_to)


def toggle_equipment_favorite(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')
    equipment = get_object_or_404(Equipment, pk=pk)
    fav, created = EquipmentFavorite.objects.get_or_create(user=request.user, equipment=equipment)
    if not created:
        fav.delete()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'index'
    return redirect(next_url)


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
