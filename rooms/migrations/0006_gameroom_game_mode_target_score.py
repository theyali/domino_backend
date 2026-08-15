from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0005_roomplayer_user_active_gift"),
    ]

    operations = [
        migrations.AddField(
            model_name="gameroom",
            name="game_mode",
            field=models.CharField(
                choices=[("101", "101"), ("phone", "Телефон")],
                default="101",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="gameroom",
            name="target_score",
            field=models.PositiveSmallIntegerField(default=101),
        ),
    ]
