from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from equipment.premium_sync import refresh_equipment_premium_for_user

from .models import DealerMembership, Payment, PaymentStatus
from .services.fulfillment import fulfill_billing_payment


@receiver(post_save, sender=Payment)
def on_billing_payment_saved(sender, instance, created, update_fields, **kwargs):
    if instance.status != PaymentStatus.SUCCESS or not instance.paid_at:
        return
    if update_fields is not None and not created:
        if "status" not in update_fields and "paid_at" not in update_fields:
            return

    def _run():
        fulfill_billing_payment(instance)

    transaction.on_commit(_run)


@receiver(post_save, sender=DealerMembership)
def on_dealer_membership_saved(sender, instance, **kwargs):
    uid = instance.user_id
    if not uid:
        return

    def _run():
        from django.contrib.auth import get_user_model

        refresh_equipment_premium_for_user(
            get_user_model().objects.get(pk=uid)
        )

    transaction.on_commit(_run)
