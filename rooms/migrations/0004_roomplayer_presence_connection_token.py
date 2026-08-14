from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0003_roomplayer_presence"),
    ]

    operations = [
        migrations.AddField(
            model_name="roomplayer",
            name="presence_connection_token",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
