from django.db import models

class User(models.Model):
    name = models.CharField(max_length=100, verbose_name="이름")
    phone = models.CharField(max_length=20, verbose_name="연락처")
    trust_score = models.IntegerField(default=50, verbose_name="신뢰 점수")

    class Meta:
        verbose_name = "회원"
        verbose_name_plural = "회원 목록"

    def __str__(self):
        return self.name
