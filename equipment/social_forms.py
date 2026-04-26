from allauth.socialaccount.forms import SignupForm
from django import forms
from django.contrib.auth.models import User

from .models import Profile


class RequiredSocialSignupForm(SignupForm):
    name = forms.CharField(
        label="이름",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "이름"}),
    )
    email = forms.EmailField(
        label="이메일",
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "이메일"}),
    )
    username = forms.CharField(
        label="아이디",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "아이디"}),
    )
    phone = forms.CharField(
        label="휴대폰번호",
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "010-0000-0000"}),
    )

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("이름을 입력하세요.")
        return name

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            raise forms.ValidationError("휴대폰번호를 입력하세요.")
        return phone

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("아이디를 입력하세요.")
        if User.objects.filter(username=username, is_active=True).exists():
            raise forms.ValidationError("이미 사용 중인 아이디입니다.")
        return username

    def save(self, request):
        user = super().save(request)
        user.is_active = True
        user.username = (self.cleaned_data.get("username") or "").strip()
        user.first_name = (self.cleaned_data.get("name") or "").strip()
        user.email = (self.cleaned_data.get("email") or "").strip()
        user.save(update_fields=["is_active", "username", "first_name", "email"])

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.phone = (self.cleaned_data.get("phone") or "").strip()
        profile.save(update_fields=["phone"])
        return user
