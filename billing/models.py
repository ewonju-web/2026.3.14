"""
굴삭기나라 유료화 DB 설계 (Django + PostgreSQL 확장 고려)

설치: INSTALLED_APPS에 'billing' 추가 후 migrate
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal


class PlacementStatus(models.TextChoices):
    """프리미엄 배치 상태. 대기열 기간은 ACTIVE 전환 시점부터 카운트."""
    WAITING = 'WAITING', '대기'
    ACTIVE = 'ACTIVE', '활성'
    EXPIRED = 'EXPIRED', '만료'
    REFUNDED = 'REFUNDED', '환불'


# --- 요금제 마스터 ---
class ProductType(models.TextChoices):
    PREMIUM_TOP = 'PREMIUM_TOP', '프리미엄 상단 노출'
    LISTING_UPGRADE = 'LISTING_UPGRADE', '판매글 업그레이드'
    DEALER_MEMBERSHIP = 'DEALER_MEMBERSHIP', '딜러 PRO 멤버십'


class SlotType(models.TextChoices):
    CATEGORY_TOP = 'CATEGORY_TOP', '카테고리 상단'
    REGION_TOP = 'REGION_TOP', '지역 상단'
    # SEARCH_TOP 폐지: 무조건 노출 금지. SEARCH_MATCH만 사용 (카테고리/지역/키워드 조건 매칭)
    SEARCH_MATCH = 'SEARCH_MATCH', '검색조건 매칭 상단'


class Product(models.Model):
    """요금제/상품 마스터"""
    code = models.CharField(max_length=32, unique=True, verbose_name='상품코드')
    name = models.CharField(max_length=100, verbose_name='상품명')
    product_type = models.CharField(
        max_length=20, choices=ProductType.choices, db_index=True, verbose_name='상품 유형'
    )
    slot_type = models.CharField(
        max_length=20, choices=SlotType.choices, blank=True, null=True,
        verbose_name='슬롯 타입 (프리미엄 상단용)'
    )
    duration_days = models.PositiveIntegerField(null=True, blank=True, verbose_name='유효 일수')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), verbose_name='판매가')
    is_recurring = models.BooleanField(default=False, verbose_name='정기결제 여부')
    is_active = models.BooleanField(default=True, verbose_name='판매 여부')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='정렬 순서')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '요금제/상품'
        verbose_name_plural = '요금제/상품'
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return f"{self.name} ({self.code})"


# --- 주문/결제 ---
class OrderStatus(models.TextChoices):
    PENDING = 'PENDING', '결제 대기'
    PAID = 'PAID', '결제 완료'
    CANCELLED = 'CANCELLED', '취소'
    REFUNDED = 'REFUNDED', '환불'


class Order(models.Model):
    """주문 (환불/취소 정책 반영)"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='billing_orders'
    )
    order_number = models.CharField(max_length=32, unique=True, db_index=True, verbose_name='주문번호')
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING, db_index=True
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    admin_memo = models.TextField(blank=True, null=True, verbose_name='운영 메모')
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='환불 금액'
    )
    refunded_at = models.DateTimeField(null=True, blank=True, verbose_name='환불 처리 시각')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '주문'
        verbose_name_plural = '주문'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} ({self.get_status_display()})"


class OrderItem(models.Model):
    """주문 항목 (어떤 상품을 어떤 대상에 적용했는지)"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='구매 시점 단가')
    # 적용 대상 (Equipment 등)
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, null=True, blank=True,
        related_name='billing_order_items'
    )
    target_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    target = GenericForeignKey('target_content_type', 'target_object_id')
    slot_type = models.CharField(max_length=20, choices=SlotType.choices, blank=True, null=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True, verbose_name='확장 데이터')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '주문 항목'
        verbose_name_plural = '주문 항목'

    def __str__(self):
        return f"OrderItem #{self.pk} {self.product.code}"


class PaymentStatus(models.TextChoices):
    REQUESTED = 'REQUESTED', '요청됨'
    SUCCESS = 'SUCCESS', '성공'
    FAILED = 'FAILED', '실패'
    CANCELLED = 'CANCELLED', '취소'


class Payment(models.Model):
    """PG 결제 기록 (환불/메모 반영)"""
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments')
    pg_provider = models.CharField(max_length=20, verbose_name='PG사')
    pg_tid = models.CharField(max_length=100, null=True, blank=True, db_index=True, verbose_name='PG 거래 ID')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.REQUESTED, db_index=True
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True, verbose_name='PG 원문 응답')
    admin_memo = models.TextField(blank=True, null=True, verbose_name='운영 메모')
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='환불 금액'
    )
    refunded_at = models.DateTimeField(null=True, blank=True, verbose_name='환불 처리 시각')

    class Meta:
        verbose_name = '결제'
        verbose_name_plural = '결제'
        ordering = ['-requested_at']

    def __str__(self):
        return f"Payment #{self.pk} {self.pg_provider} {self.status}"


# --- 프리미엄 상단 노출 (슬롯 5칸 + 대기열, 공정 정렬 paid_at ASC) ---
class PremiumPlacement(models.Model):
    """
    프리미엄 상단 노출.
    - CATEGORY_TOP: slot_no 1~5 고정 슬롯, NULL이면 대기열. 정렬은 paid_at ASC(먼저 결제 우선).
    - SEARCH_MATCH: 무조건 노출 금지. 카테고리/지역(필수) + match_keywords(선택) 조건 일치 시에만 상단 노출.
    - Payment SUCCESS 이후에만 생성. paid_at은 Payment.paid_at 복사. 대기열이면 status=WAITING, ACTIVE 전환 시 starts_at/expires_at 세팅.
    """
    equipment = models.ForeignKey(
        'equipment.Equipment', on_delete=models.CASCADE, related_name='premium_placements'
    )
    status = models.CharField(
        max_length=12,
        choices=PlacementStatus.choices,
        default=PlacementStatus.WAITING,
        db_index=True,
        verbose_name='배치 상태',
    )
    slot_type = models.CharField(max_length=20, choices=SlotType.choices, db_index=True)
    slot_no = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='슬롯 번호(1~5)',
        help_text='CATEGORY_TOP일 때 1~5 고정 슬롯. NULL이면 대기열.',
    )
    waitlist_rank = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='대기열 순서',
        help_text='표시용(정합성 원본은 paid_at ASC + id ASC).',
    )
    category = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    region_key = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    match_keywords = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='검색 매칭 키워드',
        help_text='SEARCH_MATCH: {"raw": [...], "norm": [...]}. 노출 로직은 norm 기준 매칭.',
    )
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='placements'
    )
    starts_at = models.DateTimeField(null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    paid_at = models.DateTimeField(
        db_index=True,
        verbose_name='결제 시각',
        help_text='공정 정렬(paid_at ASC). 결제 성공 시 Payment.paid_at 복사, null 불가.',
    )
    auto_renewable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    admin_memo = models.TextField(blank=True, null=True, verbose_name='운영 메모')
    refunded_at = models.DateTimeField(null=True, blank=True, verbose_name='환불 처리 시각')
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='환불 금액'
    )
    period_adjusted_at = models.DateTimeField(null=True, blank=True, verbose_name='기간 수동 조정 시각')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '프리미엄 상단 노출'
        verbose_name_plural = '프리미엄 상단 노출'
        ordering = ['paid_at', 'id']  # 공정: paid_at ASC, 분쟁 방지용 id
        indexes = [
            models.Index(fields=['slot_type', 'expires_at']),
            models.Index(fields=['slot_type', 'category', 'expires_at']),
            models.Index(fields=['slot_type', 'region_key', 'expires_at']),
            models.Index(fields=['slot_type', 'category', 'slot_no']),
            models.Index(fields=['slot_type', 'category', 'paid_at'], name='billing_pp_waitlist_paid'),
            models.Index(fields=['slot_type', 'category', 'slot_no', 'expires_at'], name='billing_pp_slot_exp'),
        ]
        constraints = [
            # slot_no가 있으면 1~5만 허용(대기열 NULL 허용).
            models.CheckConstraint(
                check=Q(slot_no__isnull=True) | (Q(slot_no__gte=1) & Q(slot_no__lte=5)),
                name='billing_pp_slot_no_range_1_5',
            ),
            # 카테고리 TOP에서 (category, slot_no) 유니크.
            models.UniqueConstraint(
                fields=['slot_type', 'category', 'slot_no'],
                condition=Q(slot_type=SlotType.CATEGORY_TOP, slot_no__isnull=False),
                name='billing_placement_category_slot_unique',
            ),
        ]

    def __str__(self):
        slot_info = f"slot{self.slot_no}" if self.slot_no else "대기열"
        exp = self.expires_at if self.expires_at else "-"
        return f"Placement #{self.equipment_id} {self.slot_type} {slot_info} ~ {exp}"


# --- 판매글 업그레이드 ---
class EquipmentUpgrade(models.Model):
    """매물별 업그레이드 (사진 20장, 강조, 재노출)"""
    equipment = models.OneToOneField(
        'equipment.Equipment', on_delete=models.CASCADE, related_name='upgrade'
    )
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='equipment_upgrades'
    )
    max_images = models.PositiveIntegerField(default=20, verbose_name='최대 사진 수')
    is_highlight = models.BooleanField(default=True, verbose_name='강조 표시')
    bump_at = models.DateTimeField(null=True, blank=True, verbose_name='마지막 재노출 시점')
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '매물 업그레이드'
        verbose_name_plural = '매물 업그레이드'

    def __str__(self):
        return f"Upgrade equipment#{self.equipment_id} ~ {self.expires_at}"


# --- 딜러 PRO 멤버십 ---
class DealerMembership(models.Model):
    """딜러 PRO 멤버십 (1 user 1 멤버십)"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dealer_membership'
    )
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='dealer_memberships'
    )
    period_start = models.DateField(verbose_name='구독 시작일')
    period_end = models.DateField(db_index=True, verbose_name='구독 만료일')
    is_auto_renew = models.BooleanField(default=False, verbose_name='자동 갱신')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '딜러 PRO 멤버십'
        verbose_name_plural = '딜러 PRO 멤버십'

    def __str__(self):
        return f"{self.user.username} PRO ~ {self.period_end}"

    @property
    def is_active(self):
        from django.utils import timezone
        return self.period_end >= timezone.now().date()


# --- 수익 집계 (시뮬레이션/대시보드용) ---
class RevenueDaily(models.Model):
    """일별 매출 집계 (크론으로 채움)"""
    date = models.DateField(db_index=True)
    product_code = models.CharField(max_length=32, db_index=True)
    order_count = models.PositiveIntegerField(default=0)
    amount_sum = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '일별 매출'
        verbose_name_plural = '일별 매출'
        unique_together = [('date', 'product_code')]
        ordering = ['-date', 'product_code']


# --- 전환율 분석용 이벤트 로그 ---
class ConversionEvent(models.Model):
    """전환 퍼널 분석용 이벤트 로그 (노출→클릭→결제시도→성공/실패)"""
    event_type = models.CharField(max_length=32, db_index=True, verbose_name='이벤트 유형')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversion_events',
    )
    session_key = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversion_events',
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True, verbose_name='추가 데이터')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = '전환 이벤트'
        verbose_name_plural = '전환 이벤트'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.created_at}"
