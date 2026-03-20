"""
기존(direct-nara) 이관 회원의 이름·전화번호를 리뉴얼 회원 목록(accounts.MemberProfile)에 반영.
equipment.Profile(legacy_member_id, phone, company_name) 및 User.first_name → MemberProfile(phone, company_name, ceo_name)
사용: python manage.py sync_legacy_members [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from equipment.models import Profile as EquipmentProfile
from accounts.models import MemberProfile, MembershipGrade
import re

User = get_user_model()

def looks_like_phone_number(raw):
    """이름/상호 필드에 들어가면 안 되는 전화번호 형태인지 대략 판별."""
    if not raw:
        return False
    digits = re.sub(r"[^0-9]", "", str(raw).strip())
    if not digits:
        return False
    if digits.startswith("010") and len(digits) == 11:
        return True
    if digits.startswith("0") and len(digits) in (10, 11):
        return True
    return False


class Command(BaseCommand):
    help = "기존 이관 회원의 이름·전화번호를 회원 프로필(MemberProfile)에 반영"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 저장 없이 반영할 대상만 출력",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("(dry-run: 저장하지 않음)")

        grade = MembershipGrade.objects.filter(code="normal").first()
        if not grade:
            self.stdout.write(self.style.WARNING("일반회원 등급이 없습니다. python manage.py init_grades 를 먼저 실행하세요."))
            return

        # equipment.Profile이 있는 사용자(이관 회원 또는 프로필 보유자) 기준으로 MemberProfile 동기화
        count_updated = 0
        count_created = 0
        count_skipped = 0

        for ep in EquipmentProfile.objects.select_related("user").all():
            user = ep.user
            name = (user.first_name or "").strip() or (ep.company_name or "").strip() or "회원"
            phone = (ep.phone or "").strip() or "미입력"
            company_name = (ep.company_name or "").strip()[:100] if ep.company_name else ""

            try:
                mp = MemberProfile.objects.get(user=user)
            except MemberProfile.DoesNotExist:
                mp = None

            if mp is None:
                if dry_run:
                    self.stdout.write(f"  [생성 예정] user={user.username} name={name[:20]} phone={phone[:15]}")
                else:
                    MemberProfile.objects.create(
                        user=user,
                        grade=grade,
                        phone=phone,
                        company_name=company_name,
                        ceo_name=name[:50],
                    )
                count_created += 1
                continue

            # 기존 MemberProfile: 이관 회원이면 이름/전화/상호 반영, 아니면 비어 있을 때만 채움
            if ep.legacy_member_id:
                if not dry_run:
                    mp.phone = phone
                    mp.ceo_name = name[:50]
                    mp.company_name = company_name[:100] if company_name else mp.company_name or ""
                    mp.save(update_fields=["phone", "ceo_name", "company_name", "updated_at"])
                count_updated += 1
            else:
                updated = False
                if (not mp.phone or mp.phone == "미입력") and phone and phone != "미입력":
                    if not dry_run:
                        mp.phone = phone
                    updated = True
                ceo_is_phone = looks_like_phone_number(mp.ceo_name)
                company_is_phone = looks_like_phone_number(mp.company_name)
                name_is_phone = looks_like_phone_number(name)
                company_name_is_phone = looks_like_phone_number(company_name)

                if (not mp.ceo_name or ceo_is_phone) and name and name != "회원" and not name_is_phone:
                    if not dry_run:
                        mp.ceo_name = name[:50]
                    updated = True
                if (not mp.company_name or company_is_phone) and company_name and not company_name_is_phone:
                    if not dry_run:
                        mp.company_name = company_name[:100]
                    updated = True
                if updated:
                    if not dry_run:
                        mp.save(update_fields=["phone", "ceo_name", "company_name", "updated_at"])
                    count_updated += 1
                else:
                    count_skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"회원 프로필 동기화: 생성 {count_created}, 갱신 {count_updated}, 스킵 {count_skipped}"
                + (" (dry-run)" if dry_run else "")
            )
        )
