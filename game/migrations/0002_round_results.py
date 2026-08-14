from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0002_roomplayer_is_active"),
        ("game", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="consecutive_passes",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="gamesession",
            name="last_round_result",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="gamesession",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Идёт игра"),
                    ("round_finished", "Раунд завершён"),
                    ("finished", "Матч завершён"),
                ],
                default="active",
                max_length=16,
            ),
        ),
    ]
