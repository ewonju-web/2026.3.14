from django.db import IntegrityError, transaction
from django.utils.timezone import now

from ..models import VisitorCount, VisitorLog


class VisitorCounterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        ip = self.get_client_ip(request)
        if not ip:
            return self.get_response(request)

        today = now().date()
        referer = request.META.get('HTTP_REFERER') or '직접 접속'

        try:
            with transaction.atomic():
                log, created = VisitorLog.objects.get_or_create(
                    ip_address=ip,
                    visit_date=today,
                    defaults={'referer': referer}
                )
                if created:
                    counter, _ = VisitorCount.objects.get_or_create(date=today)
                    counter.count = (counter.count or 0) + 1
                    counter.save(update_fields=['count'])
        except IntegrityError:
            pass
        except Exception:
            pass

        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return (request.META.get('REMOTE_ADDR') or '').strip()
