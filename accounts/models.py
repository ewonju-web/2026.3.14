
"""
굴삭기나라 - 회원/등급/정액제 구독 모델
DB 설계: docs/DB_MEMBERSHIP_DESIGN.md
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class MembershipGrade(models.Model):
    """등급 마스터: 일반회원, 매매상 등"""
    code = models.CharField("코드", max_length=20, unique=True)
    name = models.CharField("등급명", max_length=50)
    is_paid = models.BooleanField("유료등급", default=False)
    max_listings = models.PositiveIntegerField(
        "최대 매물 수",
        null=True,
        blank=True,
        help_text="null이면 제한 없음",
    )
    description = models.CharField("설명", max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField("정렬순서", default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "회원 등급"
        verbose_name_plural = "회원 등급"

    def __str__(self):
        return f"{self.name}({self.code})"


class MemberProfile(models.Model):
    """회원 확장 프로필 (User 1:1)"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member_profile",
        verbose_name="사용자",
    )
    grade = models.ForeignKey(
        MembershipGrade,
        on_delete=models.PROTECT,
        related_name="members",
        verbose_name="등급",
    )
    company_name = models.CharField("상호/회사명", max_length=100, blank=True)
    biz_no = models.CharField("사업자번호", max_length=20, blank=True)
    ceo_name = models.CharField("대표자명", max_length=50, blank=True)
    phone = models.CharField("연락처", max_length=20)
    phone_secondary = models.CharField("추가 연락처", max_length=20, blank=True)
    address = models.CharField("주소", max_length=200, blank=True)
    is_dealer = models.BooleanField(
        "매매상 여부",
        default=False,
        help_text="매매상(정액제) 여부 캐시",
    )
    created_at = models.DateTimeField("생성일", auto_now_add=True)
    updated_at = models.DateTimeField("수정일", auto_now=True)

    class Meta:
        verbose_name = "회원 프로필"
        verbose_name_plural = "회원 프로필"

    def __str__(self):
        return f"{self.user.username} ({self.grade.name})"

    def save(self, *args, **kwargs):
        self.is_dealer = self.grade.is_paid
        super().save(*args, **kwargs)

    def has_active_subscription(self):
        """현재 유효한 정액제 구독이 있는지"""
        if not self.is_dealer:
            return False
        return self.subscriptions.filter(
            status="active",
            expires_at__gte=timezone.now().date(),
        ).exists()


class Subscription(models.Model):
    """정액제 구독"""
    PLAN_MONTHLY = "monthly"
    PLAN_YEARLY = "yearly"
    PLAN_CHOICES = [
        (PLAN_MONTHLY, "월 구독"),
        (PLAN_YEARLY, "연 구독"),
    ]
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "이용중"),
        (STATUS_EXPIRED, "만료"),
        (STATUS_CANCELLED, "취소"),
    ]

    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name="회원",
    )
    plan = models.CharField("요금제", max_length=20, choices=PLAN_CHOICES)
    started_at = models.DateTimeField("시작일")
    expires_at = models.DateTimeField("만료일")
    status = models.CharField(
        "상태",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    pg_provider = models.CharField("PG사", max_length=50, blank=True)
    pg_uid = models.CharField("PG 결제고유번호", max_length=100, blank=True)
    amount = models.PositiveIntegerField("결제금액(원)", default=0)
    created_at = models.DateTimeField("생성일", auto_now_add=True)
    updated_at = models.DateTimeField("수정일", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "구독"
        verbose_name_plural = "구독"

    def __str__(self):
        return f"{self.member.user.username} {self.get_plan_display()} ~ {self.expires_at.date()}"

    @property
    def is_active(self):
        return (
            self.status == self.STATUS_ACTIVE
            and timezone.now() <= self.expires_at
        )


class PaymentHistory(models.Model):
    """결제 이력 (선택 사용)"""
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "성공"),
        (STATUS_FAILED, "실패"),
        (STATUS_REFUNDED, "환불"),
    ]

    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="회원",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="구독",
    )
    amount = models.PositiveIntegerField("금액(원)")
    pg_provider = models.CharField("PG사", max_length=50, blank=True)
    pg_uid = models.CharField("PG 고유번호", max_length=100, blank=True)
    status = models.CharField(
        "상태",
        max_length=20,
        choices=STATUS_CHOICES,
    )
    paid_at = models.DateTimeField("결제일시", null=True, blank=True)
    created_at = models.DateTimeField("생성일", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "결제 이력"
        verbose_name_plural = "결제 이력"

    def __str__(self):
        return f"{self.member.user.username} {self.amount}원 {self.status}"
