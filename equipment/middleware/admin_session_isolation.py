from django.contrib.auth import logout
from django.shortcuts import redirect


class AdminSessionIsolationMiddleware:
    """
    관리자 계정 세션은 /admin/ 경로에서만 유지한다.
    관리자가 일반 서비스 경로로 이동하면 즉시 로그아웃 처리해
    서비스 사용자 로그인과 관리자 로그인을 분리한다.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        path = (getattr(request, "path", "") or "").strip()

        if (
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser)
            and not path.startswith("/admin/")
        ):
            logout(request)
            return redirect("/")

        return self.get_response(request)
