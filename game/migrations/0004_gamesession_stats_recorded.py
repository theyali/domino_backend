from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0003_turn_timer"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="stats_recorded",
            field=models.BooleanField(default=False),
        ),
    ]
