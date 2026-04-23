from datetime import timedelta
from django.contrib.auth import logout
from django.utils.timezone import localdate
from .models import VisitorCount

def visitor_stats(request):
    # 운영 환경에서 미들웨어 누락/순서 문제로 관리자 세션이 프론트에 남는 경우를 방지한다.
    user = getattr(request, "user", None)
    path = (getattr(request, "path", "") or "").strip()
    if (
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser)
        and not path.startswith("/admin/")
    ):
        logout(request)

    today = localdate()
    yesterday = today - timedelta(days=1)

    today_row = VisitorCount.objects.filter(date=today).values('count', 'session_count').first() or {}
    yesterday_row = VisitorCount.objects.filter(date=yesterday).values('count', 'session_count').first() or {}

    # 기존 템플릿 호환: VISITOR_*는 30분 세션 기준 방문수 우선 사용
    today_count = today_row.get('session_count') or 0
    yesterday_count = yesterday_row.get('session_count') or 0

    return {
        "VISITOR_TODAY": today_count,
        "VISITOR_YESTERDAY": yesterday_count,
        "VISITOR_UNIQUE_TODAY": today_row.get('count') or 0,
        "VISITOR_UNIQUE_YESTERDAY": yesterday_row.get('count') or 0,
    }
