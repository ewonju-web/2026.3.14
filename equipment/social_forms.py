from allauth.socialaccount.forms import SignupForm
from django import forms

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

    def save(self, request):
        user = super().save(request)
        user.first_name = (self.cleaned_data.get("name") or "").strip()
        user.email = (self.cleaned_data.get("email") or "").strip()
        user.save(update_fields=["first_name", "email"])

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.phone = (self.cleaned_data.get("phone") or "").strip()
        profile.save(update_fields=["phone"])
        return user
