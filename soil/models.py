from django.conf import settings
from django.db import models


class SoilPost(models.Model):
    """흙 받으실분/흙 드립니다 게시글. 1차는 need(수요)만 노출, 추후 offer 확장."""

    class PostType(models.TextChoices):
        NEED = 'need', '흙 받으실분'
        OFFER = 'offer', '흙 드립니다'

    post_type = models.CharField(
        max_length=10,
        choices=PostType.choices,
        default=PostType.NEED,
        verbose_name='유형',
    )
    title = models.CharField(max_length=200, verbose_name='제목')
    location = models.CharField(max_length=100, verbose_name='지역')
    quantity = models.CharField(max_length=200, blank=True, verbose_name='수량')
    soil_type = models.CharField(max_length=100, blank=True, verbose_name='흙 종류')
    description = models.TextField(blank=True, verbose_name='내용')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='soil_posts',
        verbose_name='작성자',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='작성일')
    is_active = models.BooleanField(default=True, verbose_name='활성')

    class Meta:
        verbose_name = '흙 게시글'
        verbose_name_plural = '흙 게시글'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
