from django import forms
from .models import SoilPost


class SoilPostForm(forms.ModelForm):
    class Meta:
        model = SoilPost
        fields = ('title', 'location', 'quantity', 'soil_type', 'description')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 성토용 흙 필요합니다'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 경기 남양주'}),
            'quantity': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 25톤 덤프 10대분'}),
            'soil_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 성토용/마사토/혼합'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '추가 설명 (선택)'}),
        }
