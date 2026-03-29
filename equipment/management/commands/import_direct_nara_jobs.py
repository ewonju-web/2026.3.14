# -*- coding: utf-8 -*-
"""
direct-nara tb_guinout → JobPost 이관 (기본: 최근 N개월만).

  python manage.py import_direct_nara_jobs
  python manage.py import_direct_nara_jobs --months 8 --dry-run
  python manage.py import_direct_nara_jobs --months 12 --limit 500
  python manage.py import_direct_nara_jobs --sql-dump   # 프로젝트 내 db_backup_20260308.sql 만 사용
  python manage.py import_direct_nara_jobs --sql-dump C:\\path\\dump.sql

MySQL(direct_nara) 우선; 연결 실패 시 backups/.../db_backup_20260308.sql 이 있으면 자동으로 덤프에서 읽습니다.
--sql-dump 를 주면 MySQL을 쓰지 않고 지정(또는 기본) 덤프만 사용합니다.
"""
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from equipment.models import JobPost, Profile
from .import_direct_nara import normalize_phone, run_sql
from ._guinout_sql_parse import iter_tb_guinout_rows_from_dump


def _parse_legacy_datetime(s):
    if not s or str(s).strip().startswith("0000"):
        return None
    raw = str(s).strip()[:19]
    dt = parse_datetime(raw)
    if dt is None:
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                dt = datetime.strptime(raw[:10], "%Y-%m-%d")
            except ValueError:
                return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_deadline(edate):
    if not edate or not str(edate).strip():
        return None
    s = str(edate).strip()[:10]
    if not s or s.startswith("0000"):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_recruit_count(incount):
    if not incount:
        return None
    s = str(incount).strip()
    if s.isdigit():
        return int(s)
    return None


def _project_default_sql_path():
    return (
        Path(settings.BASE_DIR)
        / "backups"
        / "restore-20260311"
        / "direct_nara_backup"
        / "db_backup_20260308.sql"
    )


def _row_from_guinout_vals(vals):
    """32칼럼 vals → import 루프용 튜플."""
    if len(vals) < 32:
        return None
    uid, title, mode = vals[0], vals[1], vals[2]
    viewtype = vals[3]
    lcode, city, county = vals[4], vals[5], vals[6]
    title1, incount, edate, spack = vals[7], vals[8], vals[9], vals[10]
    pay, content = vals[14], vals[15]
    cname, uname = vals[17], vals[18]
    utel, uaddr1, uaddr2 = vals[21], vals[23], vals[24]
    reg_date = vals[31]
    return (
        uid,
        title,
        mode,
        lcode,
        city,
        county,
        title1,
        incount,
        edate,
        spack,
        pay,
        content,
        cname,
        uname,
        utel,
        uaddr1,
        uaddr2,
        reg_date,
        viewtype,
    )


def _load_rows_from_sql_dump(path: str, cutoff_str: str, limit: int):
    """viewtype=Y, reg_date 유효·cutoff 이상, uid 오름차순, limit."""
    rows = []
    for vals in iter_tb_guinout_rows_from_dump(path):
        mapped = _row_from_guinout_vals(vals)
        if mapped is None:
            continue
        *rest, viewtype = mapped
        if (viewtype or "").strip() != "Y":
            continue
        reg_date = rest[-1]
        rs = str(reg_date or "").strip()
        if not rs or rs.startswith("0000"):
            continue
        if len(rs) >= 19:
            if rs[:19] < cutoff_str[:19]:
                continue
        elif len(rs) >= 10:
            if rs[:10] < cutoff_str[:10]:
                continue
        rows.append(mapped[:-1])

    def sort_key(r):
        u = r[0]
        try:
            return int(u)
        except (TypeError, ValueError):
            return 0

    rows.sort(key=sort_key)
    if limit < 999999:
        rows = rows[:limit]
    return rows


class Command(BaseCommand):
    help = "direct-nara tb_guinout → JobPost (기본 최근 8개월, viewtype=Y만)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=8,
            help="reg_date 기준 최근 N개월 글만 이관 (기본 8)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="저장 없이 건수만 출력",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="최대 이관 건수 (0=제한 없음)",
        )
        parser.add_argument(
            "--sql-dump",
            nargs="?",
            const="__project_default__",
            default=None,
            metavar="PATH",
            help="MySQL 대신 mysqldump 파일만 사용. 경로 생략 시 프로젝트 내 db_backup_20260308.sql",
        )

    def handle(self, *args, **options):
        months = max(1, options["months"])
        dry_run = options["dry_run"]
        limit = options["limit"] or 999999
        sql_dump_opt = options["sql_dump"]

        cutoff = timezone.now() - timedelta(days=30 * months)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

        dump_path = None
        if sql_dump_opt == "__project_default__":
            p = _project_default_sql_path()
            dump_path = str(p) if p.is_file() else None
            if not dump_path:
                self.stderr.write("기본 SQL 덤프가 없습니다: %s" % p)
                return
        elif sql_dump_opt:
            dump_path = sql_dump_opt.strip()
            if not Path(dump_path).is_file():
                self.stderr.write("sql-dump 파일이 없습니다: %s" % dump_path)
                return

        rows = None
        source_label = "tb_guinout"

        if dump_path:
            self.stdout.write("SQL 덤프에서 읽습니다: %s" % dump_path)
            rows = _load_rows_from_sql_dump(dump_path, cutoff_str, limit)
            source_label = "tb_guinout (sql)"
        else:
            try:
                from django.db import connections

                connections["direct_nara"].ensure_connection()
            except Exception as e:
                auto = _project_default_sql_path()
                if auto.is_file():
                    self.stdout.write(
                        "direct_nara DB 연결 실패, SQL 덤프로 대체합니다: %s (%s)"
                        % (auto, e)
                    )
                    dump_path = str(auto)
                    rows = _load_rows_from_sql_dump(dump_path, cutoff_str, limit)
                    source_label = "tb_guinout (sql fallback)"
                else:
                    self.stderr.write(
                        "direct_nara DB 연결 실패. settings.DATABASES['direct_nara'] 확인. %s" % e
                    )
                    return
            if rows is None:
                sql = """
                    SELECT uid, title, mode, lcode, city, county, title1, incount, edate, spack, pay, content,
                           cname, uname, utel, uaddr1, uaddr2, reg_date
                    FROM tb_guinout
                    WHERE viewtype = 'Y'
                      AND reg_date > '0000-00-00 00:00:00'
                      AND reg_date >= %s
                    ORDER BY uid
                """
                rows = run_sql("direct_nara", sql, [cutoff_str])
                if limit < 999999:
                    rows = rows[:limit]

        self.stdout.write(
            "%s 후보 %d건 (reg_date >= %s, 최근 약 %d개월)"
            % (source_label, len(rows), cutoff_str, months)
        )

        phone_to_user = {}
        for p in Profile.objects.select_related("user").exclude(phone__isnull=True).exclude(phone=""):
            ph = normalize_phone(p.phone)
            if ph:
                phone_to_user[ph] = p.user

        created = 0
        skipped = 0

        for row in rows:
            (
                uid,
                title,
                mode,
                lcode,
                city,
                county,
                title1,
                incount,
                edate,
                spack,
                pay,
                content,
                cname,
                uname,
                utel,
                uaddr1,
                uaddr2,
                reg_date,
            ) = row

            try:
                uid_int = int(uid)
            except (TypeError, ValueError):
                skipped += 1
                continue

            if JobPost.objects.filter(legacy_guin_uid=uid_int).exists():
                skipped += 1
                continue

            mode_s = str(mode or "").strip()
            if mode_s == "2":
                job_type = "SEEKING"
            else:
                job_type = "HIRING"

            region_sido = str(city or "")[:50]
            county_s = str(county or "").strip()
            if county_s in ("", "- 구/군 -", "-구/군-"):
                region_sigungu = ""
            else:
                region_sigungu = county_s[:50]

            location = ("%s %s" % (city or "", county or "")).strip()[:100]
            title1_s = str(title1 or "")
            doc_resident = "주민" in title1_s
            doc_license = "면허" in title1_s

            author = None
            if utel:
                ph = normalize_phone(str(utel))
                if ph:
                    author = phone_to_user.get(ph)

            addr = (str(uaddr1 or "") + " " + str(uaddr2 or "")).strip()[:300]
            deadline = _parse_deadline(edate)
            deadline_type = "DATE" if deadline else "UNTIL_FILLED"
            reg_dt = _parse_legacy_datetime(reg_date)

            if dry_run:
                created += 1
                continue

            jp = JobPost.objects.create(
                legacy_guin_uid=uid_int,
                job_type=job_type,
                title=str(title or "")[:200] or "제목없음",
                location=location,
                region_sido=region_sido,
                region_sigungu=region_sigungu,
                equipment_type=str(lcode or "")[:100],
                pay=str(pay or "")[:100],
                content=str(content or ""),
                contact=str(utel or "")[:50],
                deadline=deadline,
                deadline_type=deadline_type,
                experience=str(spack or "")[:50],
                writer_display=str(cname or uname or "")[:50] or "이관",
                author=author,
                password_hash="",
                recruit_count=_parse_recruit_count(incount),
                doc_resident=doc_resident,
                doc_license=doc_license,
                company_name=str(cname or "")[:200] if job_type == "HIRING" else "",
                company_address=addr if job_type == "HIRING" else "",
            )
            if reg_dt:
                JobPost.objects.filter(pk=jp.pk).update(created_at=reg_dt)
            created += 1

        if dry_run:
            self.stdout.write(
                "dry-run: 이관 대상(신규) %d건, 스킵(이미 legacy_guin_uid 있음) %d건" % (created, skipped)
            )
        else:
            self.stdout.write("이관 생성 %d건, 스킵 %d건" % (created, skipped))
