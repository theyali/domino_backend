import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("restaurants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameRoom",
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
                ("name", models.CharField(blank=True, max_length=80)),
                ("owner_name", models.CharField(max_length=40)),
                (
                    "max_players",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(2),
                            django.core.validators.MaxValueValidator(4),
                        ]
                    ),
                ),
                ("password_hash", models.CharField(blank=True, max_length=128)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("waiting", "Ожидание"),
                            ("playing", "Игра"),
                            ("finished", "Завершена"),
                        ],
                        default="waiting",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "restaurant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="game_rooms",
                        to="restaurants.restaurant",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="RoomPlayer",
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
                ("name", models.CharField(max_length=40)),
                ("seat_index", models.PositiveSmallIntegerField()),
                ("is_owner", models.BooleanField(default=False)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="players",
                        to="rooms.gameroom",
                    ),
                ),
            ],
            options={"ordering": ["seat_index"]},
        ),
        migrations.AddConstraint(
            model_name="roomplayer",
            constraint=models.UniqueConstraint(
                fields=("room", "seat_index"),
                name="unique_room_seat",
            ),
        ),
    ]
