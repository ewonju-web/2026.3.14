from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.auth import logout
from django.http import HttpResponseRedirect
from equipment.views import user_login, user_logout, signup, check_username, find_username


def _social_callback_alias(request, provider: str):
    """Developer console callback aliases -> allauth callback URL."""
    provider = (provider or "").strip().lower()
    if provider not in ("kakao", "naver"):
        return HttpResponseRedirect("/login/")
    query = request.META.get("QUERY_STRING", "")
    target = f"/accounts/{provider}/login/callback/"
    if query:
        target = f"{target}?{query}"
    return HttpResponseRedirect(target)


def _admin_view_site(request):
    """
    관리자 상단 '사이트 보기' 전용:
    관리자 세션을 먼저 종료한 뒤 메인으로 이동한다.
    """
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        logout(request)

    response = HttpResponseRedirect("/")
    cookie_name = settings.SESSION_COOKIE_NAME
    host = (request.get_host() or "").split(":")[0].strip().lower()

    paths = {"/", "/admin"}
    if settings.SESSION_COOKIE_PATH:
        paths.add(settings.SESSION_COOKIE_PATH)

    domains = {None}
    if settings.SESSION_COOKIE_DOMAIN:
        domains.add(settings.SESSION_COOKIE_DOMAIN)
    if host:
        domains.add(host)
        domains.add(f".{host}")
    # 운영에서 실제 사용 중인 호스트들까지 함께 만료해 쿠키 잔존 이슈를 줄인다.
    domains.update({"211.110.140.201", "s2022.co.kr", ".s2022.co.kr", "www.s2022.co.kr", ".www.s2022.co.kr"})

    for domain in domains:
        for path in paths:
            response.delete_cookie(cookie_name, path=path, domain=domain)

    return response


admin.site.site_url = "/admin/view-site/"

urlpatterns = [
    path('admin/view-site/', _admin_view_site, name='admin_view_site'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # 소셜 로그인: /accounts/login/ 에서 카카오/네이버
    # 소셜 콜백 별칭: 개발자센터 등록 URL을 /auth/... 로 써도 동작하게 함
    path('auth/kakao/callback', lambda request: _social_callback_alias(request, 'kakao')),
    path('auth/naver/callback', lambda request: _social_callback_alias(request, 'naver')),
    path('chat/', include('chat.urls')),
    path('soil/', include('soil.urls')),
    path('', include('equipment.urls')),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('signup/check-username/', check_username, name='check_username'),
    path('signup/', signup, name='signup'),
    path('find-username/', find_username, name='find_username'),
    # 비밀번호 찾기(재설정)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url='/password-reset/done/'
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/password-reset-complete/'
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
