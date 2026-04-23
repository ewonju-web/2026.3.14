from django import forms
from .models import SoilPost


class SoilPostForm(forms.ModelForm):
    class Meta:
        model = SoilPost
        fields = ('post_type', 'material_type', 'title', 'quantity', 'location', 'contact', 'note', 'description', 'image')
        widgets = {
            'post_type': forms.Select(attrs={'class': 'form-select'}),
            'material_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 성토용 흙 나눔합니다'}),
            'quantity': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 약 5톤, 트럭 2대 분량'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 경기 남양주'}),
            'contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 010-1234-5678'}),
            'note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 평일 오전 상차 가능'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '상세내용을 입력해 주세요.'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
