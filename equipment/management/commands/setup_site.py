# -*- coding: utf-8 -*-
"""
Django Sites 프레임워크에 현재 사이트 도메인 연결.
배포 후 한 번 실행: python manage.py setup_site
.env 의 SITE_DOMAIN, SITE_NAME 이 있으면 사용, 없으면 settings 기본값.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'SITE_ID에 해당하는 Site의 domain/name을 설정해 사이트를 연결합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            type=str,
            default=getattr(settings, 'SITE_DOMAIN', 's2022.co.kr'),
            help='사이트 도메인 (예: s2022.co.kr)',
        )
        parser.add_argument(
            '--name',
            type=str,
            default=getattr(settings, 'SITE_NAME', '굴삭기나라'),
            help='사이트 표시 이름',
        )

    def handle(self, *args, **options):
        domain = options['domain'].strip()
        name = options['name'].strip()
        site_id = getattr(settings, 'SITE_ID', 1)

        site, created = Site.objects.get_or_create(
            id=site_id,
            defaults={'domain': domain, 'name': name},
        )
        if not created and (site.domain != domain or site.name != name):
            site.domain = domain
            site.name = name
            site.save()
            self.stdout.write(self.style.SUCCESS(f'Site(id={site_id}) 갱신: {domain} / {name}'))
        elif created:
            self.stdout.write(self.style.SUCCESS(f'Site(id={site_id}) 생성: {domain} / {name}'))
        else:
            self.stdout.write(f'Site(id={site_id}) 이미 설정됨: {site.domain} / {site.name}')
        self.stdout.write(f'사이트 연결 완료. 소셜 로그인 콜백 URL: https://{domain}/accounts/.../callback/')
