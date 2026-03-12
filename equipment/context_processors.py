from datetime import timedelta
from django.utils.timezone import localdate
from .models import VisitorCount

def visitor_stats(request):
    today = localdate()
    yesterday = today - timedelta(days=1)

    today_count = VisitorCount.objects.filter(date=today).values_list('count', flat=True).first() or 0
    yesterday_count = VisitorCount.objects.filter(date=yesterday).values_list('count', flat=True).first() or 0

    return {
        "VISITOR_TODAY": today_count,
        "VISITOR_YESTERDAY": yesterday_count,
    }
