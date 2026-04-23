from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0040_visitor_session_count_and_session_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="listing_purge_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="매물 삭제 예정 시각"),
        ),
        migrations.AddField(
            model_name="profile",
            name="withdrawn_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="탈퇴 처리 시각"),
        ),
    ]
