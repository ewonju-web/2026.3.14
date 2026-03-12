# -*- coding: utf-8 -*-
"""
기존 direct-nara 백업의 매물 이미지(upload/pro) → 리뉴얼 EquipmentImage 이관.

파일 규칙: {uid}.jpg, {uid}_1.jpg, {uid}_2.jpg ... (uid = tb_pro.uid = Equipment.legacy_listing_id)
사용법:
  python manage.py import_direct_nara_images
  python manage.py import_direct_nara_images --source /path/to/upload/pro
  python manage.py import_direct_nara_images --dry-run --limit 50
"""
import os
import re
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from equipment.models import Equipment, EquipmentImage


# upload/pro 파일명: 12345.jpg, 12345_1.jpg, 12345_2.jpg ...
def parse_uid_from_filename(name):
    base = os.path.splitext(name)[0]
    if re.match(r"^\d+$", base):
        return int(base)
    m = re.match(r"^(\d+)_\d+$", base)
    if m:
        return int(m.group(1))
    return None


def list_image_files(source_dir):
    """source_dir 아래에서 uid와 매칭되는 이미지 파일만 (확장자 제한)."""
    allowed = (".jpg", ".jpeg", ".png", ".gif", ".webp")
    by_uid = {}
    for f in Path(source_dir).iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in allowed:
            continue
        uid = parse_uid_from_filename(f.name)
        if uid is None:
            continue
        by_uid.setdefault(uid, []).append(f)
    # 대표 이미지(uid.jpg) 먼저, 그 다음 uid_1, uid_2 순
    def sort_key(p):
        base = p.stem
        if re.match(r"^\d+$", base):
            return (0, 0)
        m = re.match(r"^(\d+)_(\d+)$", base)
        return (1, int(m.group(2))) if m else (2, 0)

    for uid in by_uid:
        by_uid[uid].sort(key=sort_key)
    return by_uid


class Command(BaseCommand):
    help = "direct-nara 백업 upload/pro 이미지 → EquipmentImage 이관 (legacy_listing_id 매칭)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=str,
            default="/srv/excavator/direct_nara_backup/upload/pro",
            help="이미지 소스 디렉터리 (upload/pro)",
        )
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 건수만 출력")
        parser.add_argument("--limit", type=int, default=0, help="처리할 매물(uid) 수 제한 (0=전체)")

    def handle(self, *args, **options):
        source = options["source"]
        dry_run = options["dry_run"]
        limit = options["limit"] or 999999

        if not os.path.isdir(source):
            self.stderr.write("소스 디렉터리가 없습니다: %s" % source)
            return

        by_uid = list_image_files(source)
        total_files = sum(len(files) for files in by_uid.values())
        self.stdout.write("소스 이미지: uid %d개, 파일 %d개" % (len(by_uid), total_files))

        # legacy_listing_id 있는 Equipment만
        eqs = {e.legacy_listing_id: e for e in Equipment.objects.filter(legacy_listing_id__isnull=False)}
        self.stdout.write("legacy_listing_id 매칭 Equipment: %d개" % len(eqs))

        media_root = Path(settings.MEDIA_ROOT)
        upload_subdir = "equipment_images"
        dest_dir = media_root / upload_subdir
        if not dry_run and not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)

        created = 0
        skipped_no_equipment = 0
        skipped_has_images = 0
        uids_done = 0

        for uid, files in sorted(by_uid.items()):
            if uids_done >= limit:
                break
            equipment = eqs.get(uid)
            if not equipment:
                skipped_no_equipment += len(files)
                continue
            # 이미 이미지가 있으면 스킵 (idempotent)
            if equipment.images.exists():
                skipped_has_images += len(files)
                continue
            uids_done += 1
            for idx, path in enumerate(files):
                if dry_run:
                    created += 1
                    continue
                # 고유 파일명: legacy_{uid}_{idx}.{ext}
                ext = path.suffix.lower()
                if ext == ".jpeg":
                    ext = ".jpg"
                new_name = "legacy_%s_%s%s" % (uid, idx, ext)
                dest_path = dest_dir / new_name
                try:
                    shutil.copy2(str(path), str(dest_path))
                except Exception as e:
                    self.stderr.write("복사 실패 %s: %s" % (path.name, e))
                    continue
                rel_path = os.path.join(upload_subdir, new_name)
                EquipmentImage.objects.create(equipment=equipment, image=rel_path)
                created += 1

        self.stdout.write(
            "이미지 이관: 생성 %d, 매물없음 스킵 %d, 이미있음 스킵 %d"
            % (created, skipped_no_equipment, skipped_has_images)
        )
