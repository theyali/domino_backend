import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("rooms", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Идёт игра"),
                            ("finished", "Завершена"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("round_number", models.PositiveSmallIntegerField(default=1)),
                ("version", models.PositiveIntegerField(default=1)),
                ("opening_domino_id", models.PositiveSmallIntegerField()),
                ("hands", models.JSONField(default=dict)),
                ("boneyard", models.JSONField(default=list)),
                ("table", models.JSONField(default=list)),
                ("scores", models.JSONField(default=dict)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "current_player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="current_turn_sessions",
                        to="rooms.roomplayer",
                    ),
                ),
                (
                    "opening_player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="opening_sessions",
                        to="rooms.roomplayer",
                    ),
                ),
                (
                    "room",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="game_session",
                        to="rooms.gameroom",
                    ),
                ),
            ],
        ),
    ]
