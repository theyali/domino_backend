from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0002_roomplayer_is_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="roomplayer",
            name="is_online",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="roomplayer",
            name="last_seen_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
