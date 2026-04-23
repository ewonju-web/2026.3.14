from django.core.management.base import BaseCommand
from django.utils import timezone

from equipment.models import Equipment, Profile


class Command(BaseCommand):
    help = "탈퇴 회원의 보관 기한(6개월)이 지난 매물을 삭제합니다."

    def handle(self, *args, **options):
        now_ts = timezone.now()
        targets = (
            Profile.objects.filter(
                withdrawn_at__isnull=False,
                listing_purge_at__isnull=False,
                listing_purge_at__lte=now_ts,
            )
            .select_related("user")
        )

        total_profiles = 0
        total_deleted = 0
        for profile in targets:
            user = profile.user
            deleted_count, _ = Equipment.objects.filter(author=user).delete()
            total_profiles += 1
            total_deleted += deleted_count
            profile.listing_purge_at = None
            profile.save(update_fields=["listing_purge_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"processed_profiles={total_profiles}, deleted_records={total_deleted}"
            )
        )
