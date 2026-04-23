from django.db import IntegrityError, transaction
from django.utils.timezone import now

from ..models import VisitorCount, VisitorLog, VisitorSession


class VisitorCounterMiddleware:
    SESSION_TIMEOUT_SECONDS = 30 * 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        ip = self.get_client_ip(request)
        if not ip:
            return self.get_response(request)

        current_time = now()
        today = current_time.date()
        referer = request.META.get('HTTP_REFERER') or '직접 접속'

        try:
            with transaction.atomic():
                _, created = VisitorLog.objects.get_or_create(
                    ip_address=ip,
                    visit_date=today,
                    defaults={'referer': referer}
                )
                counter, _ = VisitorCount.objects.get_or_create(date=today)
                if created:
                    counter.count = (counter.count or 0) + 1

                session, session_created = VisitorSession.objects.select_for_update().get_or_create(
                    ip_address=ip,
                    defaults={'last_seen_at': current_time}
                )
                is_new_session = session_created or (
                    (current_time - session.last_seen_at).total_seconds() >= self.SESSION_TIMEOUT_SECONDS
                )
                if is_new_session:
                    counter.session_count = (counter.session_count or 0) + 1

                session.last_seen_at = current_time
                session.save(update_fields=['last_seen_at'])
                counter.save(update_fields=['count', 'session_count'])
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
