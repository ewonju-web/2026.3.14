from django.conf import settings
from django.db import models


class SoilPost(models.Model):
    """현장 자재 나눔/수거 게시글."""

    class PostType(models.TextChoices):
        GIVE = 'give', '나눔 (드립니다)'
        TAKE = 'take', '수거 (가져가실분)'

    class MaterialType(models.TextChoices):
        SOIL = 'soil', '흙·토사'
        SAND = 'sand', '모래'
        GRAVEL = 'gravel', '자갈'
        CRUSHED = 'crushed', '잔석·쇄석'
        BLOCK = 'block', '블록·벽돌'
        CONCRETE = 'concrete', '콘크리트 잔재'
        OTHER = 'other', '기타 자재'

    post_type = models.CharField(
        max_length=10,
        choices=PostType.choices,
        default=PostType.GIVE,
        verbose_name='게시 유형',
    )
    material_type = models.CharField(
        max_length=20,
        choices=MaterialType.choices,
        default=MaterialType.SOIL,
        verbose_name='자재 유형',
    )
    title = models.CharField(max_length=200, verbose_name='제목')
    location = models.CharField(max_length=100, verbose_name='지역')
    quantity = models.CharField(max_length=100, blank=True, verbose_name='수량')
    contact = models.CharField(max_length=100, blank=True, verbose_name='연락처')
    note = models.CharField(max_length=200, blank=True, verbose_name='메모')
    soil_type = models.CharField(max_length=100, blank=True, verbose_name='흙 종류')
    description = models.TextField(blank=True, verbose_name='상세내용')
    image = models.ImageField(upload_to='soil_posts/', blank=True, null=True, verbose_name='사진')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='soil_posts',
        verbose_name='작성자',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='작성일')
    is_active = models.BooleanField(default=True, verbose_name='활성')

    class Meta:
        verbose_name = '현장 자재 글'
        verbose_name_plural = '현장 자재 글'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
