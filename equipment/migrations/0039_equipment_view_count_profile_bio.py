from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0038_equipment_unclaimed_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipment",
            name="view_count",
            field=models.PositiveIntegerField(default=0, verbose_name="조회수"),
        ),
        migrations.AddField(
            model_name="profile",
            name="bio",
            field=models.TextField(blank=True, default="", verbose_name="소개글"),
        ),
    ]
