"""운영: 매물을 미연결 상태로 두고 연락처(숫자만)를 저장해 '내 매물 찾기'로 연결 가능하게 함."""

from django.core.management.base import BaseCommand, CommandError

from equipment.claim_utils import normalize_phone_digits
from equipment.models import Equipment


class Command(BaseCommand):
    help = "매물 author 제거 + unclaimed_phone_norm 설정 (또는 전화만 수정)"

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, required=True, dest="pk", help="Equipment PK")
        parser.add_argument("--phone", type=str, required=True, help="연락처 (숫자만 저장)")
        parser.add_argument(
            "--clear-author",
            action="store_true",
            help="작성자를 비움(미연결 매물로 전환)",
        )

    def handle(self, *args, **options):
        pk = options["pk"]
        phone = normalize_phone_digits(options["phone"])
        if not phone:
            raise CommandError("유효한 전화번호가 아닙니다.")
        try:
            eq = Equipment.objects.get(pk=pk)
        except Equipment.DoesNotExist as e:
            raise CommandError(f"매물 {pk} 없음") from e

        eq.unclaimed_phone_norm = phone
        update_fields = ["unclaimed_phone_norm"]
        if options["clear_author"]:
            eq.author = None
            update_fields = ["author", "unclaimed_phone_norm"]
        eq.save(update_fields=update_fields)
        self.stdout.write(self.style.SUCCESS(f"OK equipment={pk} unclaimed_phone_norm={phone} author={eq.author_id}"))
