from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0039_equipment_view_count_profile_bio"),
    ]

    operations = [
        migrations.AddField(
            model_name="visitorcount",
            name="session_count",
            field=models.IntegerField(default=0, verbose_name="방문 수(30분 재방문 포함)"),
        ),
        migrations.CreateModel(
            name="VisitorSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ip_address", models.GenericIPAddressField(unique=True, verbose_name="아이피 주소")),
                ("last_seen_at", models.DateTimeField(verbose_name="마지막 방문 시각")),
            ],
            options={
                "verbose_name": "방문 세션 상태",
                "verbose_name_plural": "6. 방문 세션 상태",
            },
        ),
    ]
