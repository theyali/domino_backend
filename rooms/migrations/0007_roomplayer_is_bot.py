from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0006_gameroom_game_mode_target_score"),
    ]

    operations = [
        migrations.AddField(
            model_name="roomplayer",
            name="is_bot",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
