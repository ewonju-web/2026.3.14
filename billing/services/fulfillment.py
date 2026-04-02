"""
결제 성공 시 주문 처리: 딜러 PRO(멤버십) → DealerMembership + equipment.Profile 유료 동기화.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from equipment.premium_sync import refresh_equipment_premium_for_user

from ..models import (
    DealerMembership,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    ProductType,
)


def fulfill_billing_payment(payment: Payment) -> None:
    """Payment 가 SUCCESS 이고 paid_at 이 있을 때 한 번만(멱등) 처리."""
    if payment.status != PaymentStatus.SUCCESS or not payment.paid_at:
        return

    order = payment.order
    paid_date = payment.paid_at.date()

    with transaction.atomic():
        if order.status != OrderStatus.PAID:
            order.status = OrderStatus.PAID
            order.save(update_fields=["status", "updated_at"])

        for item in order.items.select_related("product"):
            product = item.product
            if product.product_type != ProductType.DEALER_MEMBERSHIP:
                continue

            days = product.duration_days or 30

            dm = DealerMembership.objects.filter(user_id=order.user_id).first()
            if dm is None:
                end = paid_date + timedelta(days=days)
                DealerMembership.objects.create(
                    user=order.user,
                    order_item=item,
                    period_start=paid_date,
                    period_end=end,
                    is_auto_renew=product.is_recurring,
                )
            else:
                # 갱신: 남은 기간이 있으면 그 이후부터 기간 연장
                base = max(dm.period_end, paid_date)
                new_end = base + timedelta(days=days)
                dm.order_item = item
                dm.period_end = new_end
                dm.is_auto_renew = product.is_recurring or dm.is_auto_renew
                dm.save(
                    update_fields=[
                        "order_item",
                        "period_end",
                        "is_auto_renew",
                        "updated_at",
                    ]
                )

    refresh_equipment_premium_for_user(order.user)
