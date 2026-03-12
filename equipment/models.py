from django.conf import settings
from django.db import models
from django.contrib.auth.models import User, Group


class Profile(models.Model):
    """
    사용자 프로필. 딜러 표시(매매상 배지)는 user_type == DEALER.
    PRO 혜택/노출 가중치는 billing.DealerMembership.is_active 로 구분.
    """
    USER_TYPE_CHOICES = (
        ('PERSONAL', '개인'),
        ('DEALER', '매매상'),
    )
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="사용자")
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='PERSONAL', verbose_name="사용자 유형")
    company_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="상호명")  # ✅ null 허용 (마이그레이션 멈춤 방지)
    business_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="등록번호")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="연락처")
    is_approved = models.BooleanField(default=False, verbose_name="승인여부")
    youtube_url = models.URLField(blank=True, null=True, verbose_name='유튜브 채널 주소')

    class Meta:
        verbose_name = "사용자 프로필"
        verbose_name_plural = "1. 사용자 프로필 관리"

    def __str__(self):
        return f"{self.user.username} ({self.get_user_type_display()})"


class ListingStatus(models.TextChoices):
    NORMAL = 'NORMAL', '정상 노출'
    EXPIRED_HIDDEN = 'EXPIRED_HIDDEN', '만료 숨김'  # 무료 30일 만료 시 삭제 대신 숨김, 1클릭 연장/업그레이드 유도


class EquipmentType(models.TextChoices):
    """기종 선택 (매물 등록 시 필수)"""
    EXCAVATOR = 'excavator', '굴삭기'
    FORKLIFT = 'forklift', '지게차'
    DUMP = 'dump', '덤프'
    LOADER = 'loader', '로더'
    ATTACHMENT = 'attachment', '어태치먼트'
    ETC = 'etc', '기타(부품)'


class EquipmentQuerySet(models.QuerySet):
    """목록/검색용: NORMAL만 노출. 상세 URL 직접 접근은 별도 허용."""

    def visible(self):
        return self.filter(listing_status=ListingStatus.NORMAL)


class Equipment(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='authored_equipment',
        verbose_name="작성자",
    )

    equipment_type = models.CharField(
        max_length=20,
        choices=EquipmentType.choices,
        default=EquipmentType.EXCAVATOR,
        verbose_name="기종",
        help_text="굴삭기/지게차/덤프/로더/어태치먼트/기타(부품)",
    )
    model_name = models.CharField(max_length=100, blank=True, default="", verbose_name="모델명")
    manufacturer = models.CharField(max_length=50, blank=True, default="", verbose_name="제조사")

    # 검색/필터 강화를 위한 추가 메타 정보
    # - 굴삭기: 타이어식/크롤러식/어태치먼트
    # - 지게차: 디젤식/전동좌식/전동입식/LPG 등
    sub_type = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="세부 유형",
        help_text="굴삭기: 타이어/크롤러/어태치먼트, 지게차: 디젤/전동/입식/LPG 등",
    )

    # 예) 굴삭기 톤수 구간, 지게차 톤수 구간
    weight_class = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="중량 구분",
    )

    # ✅ 연/월 분리 (미입력 시 null)
    year_manufactured = models.IntegerField(null=True, blank=True, verbose_name="제작년도")
    month_manufactured = models.IntegerField(null=True, blank=True, default=1, verbose_name="제작월")  # 1~12

    # ✅ 가동시간 (미입력 가능)
    operating_hours = models.IntegerField(default=0, blank=True, verbose_name="가동 시간(hr)")

    # 지게차 마스트(2단/3단 등)
    mast_type = models.CharField(
        max_length=10,
        blank=True,
        default="",
        verbose_name="마스트 타입",
        help_text="지게차 전용: 2단/3단 등",
    )

    # 기존 유지(만원 단위든 원 단위든 대표님 기존 방식 유지) — 필수
    listing_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="판매가격")
    current_location = models.CharField(max_length=100, blank=True, default="", verbose_name="현재 위치")

    # 지역 필터용 (구인구직과 동일 패턴: 시/도 + 시/군/구)
    region_sido = models.CharField(max_length=50, blank=True, default="", verbose_name="시/도")
    region_sigungu = models.CharField(max_length=50, blank=True, default="", verbose_name="시/군/구")
    # 차량번호: 입력 시 리스트/상세에 "번호등록" 뱃지 표시 (추후 조회 연동 시 vehicle_verified 등으로 확장 가능)
    vehicle_number = models.CharField(max_length=30, blank=True, default="", verbose_name="차량번호")
    description = models.CharField(max_length=50, verbose_name="상세 설명", blank=True, default="")
    is_sold = models.BooleanField(default=False, verbose_name="판매 완료 여부")
    password = models.CharField(max_length=100, blank=True, default="", verbose_name="비밀번호(수정용, 레거시)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록일")

    # 유료화 V2: 무료 만료 시 삭제 대신 EXPIRED_HIDDEN. 목록/검색은 NORMAL만. 상세 직접 URL은 연장/업그레이드 CTA 노출
    listing_status = models.CharField(
        max_length=20,
        choices=ListingStatus.choices,
        default=ListingStatus.NORMAL,
        db_index=True,
        verbose_name="노출 상태",
    )

    objects = EquipmentQuerySet.as_manager()

    class Meta:
        verbose_name = "중고 굴삭기"
        verbose_name_plural = "2. 중고 굴삭기 관리"

    def __str__(self):
        return self.model_name or self.get_equipment_type_display() or "매물"


class EquipmentImage(models.Model):
    equipment = models.ForeignKey(Equipment, related_name='images', on_delete=models.CASCADE, verbose_name="해당 장비")
    image = models.ImageField(upload_to='equipment_images/', verbose_name="장비 사진")

    class Meta:
        verbose_name = "장비 사진"
        verbose_name_plural = "3. 장비 사진 관리"


# --- 방문 통계 ---
class VisitorCount(models.Model):
    date = models.DateField(auto_now_add=True, unique=True, verbose_name="날짜")
    count = models.IntegerField(default=0, verbose_name="방문자 수")

    class Meta:
        verbose_name = "일별 방문자 수"
        verbose_name_plural = "4. 방문자 통계"


class VisitorLog(models.Model):
    ip_address = models.GenericIPAddressField(verbose_name="아이피 주소")
    visit_date = models.DateField(auto_now_add=True, verbose_name="방문 날짜")
    referer = models.TextField(null=True, blank=True, verbose_name="유입 경로")

    class Meta:
        unique_together = ('ip_address', 'visit_date')
        verbose_name = "방문 상세 기록"
        verbose_name_plural = "5. 방문 상세 로그"


# --- 강제 한글화 ---
User._meta.verbose_name = "회원"
User._meta.verbose_name_plural = "회원(User) 계정 관리"
Group._meta.verbose_name = "권한 그룹"
Group._meta.verbose_name_plural = "권한 그룹 관리"

class JobPost(models.Model):
    JOB_TYPES = [('HIRING', '사람구함'), ('SEEKING', '일자리구함')]
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobposts',
    )
    job_type = models.CharField(max_length=10, choices=JOB_TYPES, default='HIRING', verbose_name="구분")
    title = models.CharField(max_length=200, verbose_name="제목")
    location = models.CharField(max_length=100, blank=True, default='', verbose_name="지역(기타)")
    region_sido = models.CharField(max_length=50, default='', blank=True, verbose_name="시/도")
    region_sigungu = models.CharField(max_length=50, default='', blank=True, verbose_name="시/군/구")
    equipment_type = models.CharField(max_length=100, blank=True, default='', verbose_name="필요장비/경력")
    pay = models.CharField(max_length=100, blank=True, default='', verbose_name="급여/단가")
    content = models.TextField(verbose_name="상세내용", blank=True, default='')
    contact = models.CharField(max_length=50, blank=True, default='', verbose_name="연락처")
    created_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateField(null=True, blank=True, verbose_name="마감일")
    deadline_type = models.CharField(
        max_length=20,
        choices=[('DATE', '날짜'), ('UNTIL_FILLED', '채용시까지')],
        default='UNTIL_FILLED',
        verbose_name="마감 구분",
        blank=True,
    )
    experience = models.CharField(max_length=50, blank=True, default='', verbose_name="경력유무")
    writer_display = models.CharField(max_length=50, blank=True, default='', verbose_name="작성자(표시명)")
    password_hash = models.CharField(max_length=128, blank=True, default='', verbose_name="수정/삭제용 비밀번호(해시)")
    # 사람구함 전용
    recruit_count = models.PositiveIntegerField(null=True, blank=True, verbose_name="모집인원")
    doc_resident = models.BooleanField(default=True, verbose_name="제출서류_주민등록등본")
    doc_license = models.BooleanField(default=True, verbose_name="제출서류_면허증사본")
    company_name = models.CharField(max_length=200, blank=True, default='', verbose_name="회사명")
    company_address = models.CharField(max_length=300, blank=True, default='', verbose_name="주소")

    def __str__(self):
        return f"[{self.get_job_type_display()}] {self.title}"

    def check_password(self, raw_password):
        if not self.password_hash:
            return False
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)

class Part(models.Model):
    PART_CATEGORIES = [
        ('BUCKET', '바가지/버킷'),
        ('BREAKER', '뿌레카/함마'),
        ('GRAPPLE', '집게/그랩'),
        ('ETC', '기타 어테치먼트'),
    ]
    category = models.CharField(max_length=20, choices=PART_CATEGORIES, default='ETC')
    title = models.CharField(max_length=200)
    price = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    compatibility = models.CharField(max_length=100, help_text="예: 02급/06급 호환")
    description = models.TextField()
    contact = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='authored_parts',
    )

    def __str__(self):
        return self.title

class PartImage(models.Model):
    part = models.ForeignKey(Part, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='parts/')


class PartsShop(models.Model):
    """전국 굴삭기 부품점 연락처 (부품/AS 검색용)"""
    name = models.CharField(max_length=100, verbose_name="업체명")
    region = models.CharField(max_length=50, verbose_name="지역")
    contact = models.CharField(max_length=50, verbose_name="연락처")
    address = models.CharField(max_length=200, blank=True, default='', verbose_name="주소")
    note = models.CharField(max_length=200, blank=True, default='', verbose_name="비고")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "부품점"
        verbose_name_plural = "부품점(전국 연락처)"
        ordering = ['region', 'name']

    def __str__(self):
        return f"{self.name} ({self.region})"


# --- 찜(관심) ---
class EquipmentFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='equipment_favorites')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "장비 찜"
        verbose_name_plural = "장비 찜"
        unique_together = [('user', 'equipment')]

    def __str__(self):
        return f"{self.user.username} 찜 #{self.equipment_id}"


class PartFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='part_favorites')
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "부품 찜"
        verbose_name_plural = "부품 찜"
        unique_together = [('user', 'part')]

    def __str__(self):
        return f"{self.user.username} 찜(부품) #{self.part_id}"


# --- 댓글/문의 ---
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Comment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='comments')
    author_name = models.CharField(max_length=50, blank=True, verbose_name="이름(비회원)")
    content = models.TextField(verbose_name="내용")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "댓글/문의"
        verbose_name_plural = "댓글/문의"
        ordering = ['created_at']
