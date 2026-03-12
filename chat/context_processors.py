from django.db.models import Q

from .models import ChatMessage


def lang(request):
    """템플릿에서 사용할 언어 코드. 세션에 없으면 'ko'."""
    return {'LANG': request.session.get('lang', 'ko')}


def chat_unread(request):
    """로그인 사용자의 채팅 미읽음 메시지 총개수. 상단 '채팅' 메뉴 뱃지용."""
    unread_total = 0
    if getattr(request, 'user', None) and request.user.is_authenticated:
        unread_total = (
            ChatMessage.objects.filter(is_read=False)
            .exclude(sender=request.user)
            .filter(Q(room__buyer=request.user) | Q(room__seller=request.user))
            .count()
        )
    return {'unread_total': unread_total}
