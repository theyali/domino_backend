from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_recent_players(apps, schema_editor):
    RecentPlayerEncounter = apps.get_model("accounts", "RecentPlayerEncounter")
    RoomPlayer = apps.get_model("rooms", "RoomPlayer")

    room_ids = (
        RoomPlayer.objects.filter(user__isnull=False)
        .values_list("room_id", flat=True)
        .distinct()
    )

    for room_id in room_ids.iterator():
        players = list(
            RoomPlayer.objects.filter(room_id=room_id, user__isnull=False)
            .values("user_id", "joined_at")
            .order_by("joined_at", "id")
        )
        if len(players) < 2:
            continue

        played_at = max(item["joined_at"] for item in players)
        user_ids = list(dict.fromkeys(item["user_id"] for item in players))

        for user_id in user_ids:
            for other_user_id in user_ids:
                if user_id == other_user_id:
                    continue
                encounter, created = RecentPlayerEncounter.objects.get_or_create(
                    user_id=user_id,
                    other_user_id=other_user_id,
                    defaults={"last_played_at": played_at},
                )
                if not created and encounter.last_played_at < played_at:
                    encounter.last_played_at = played_at
                    encounter.save(update_fields=["last_played_at"])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rooms", "0005_roomplayer_user_active_gift"),
        ("accounts", "0003_social_features"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecentPlayerEncounter",
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
                    "last_played_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
                (
                    "other_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recent_opponent_encounters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recent_player_encounters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-last_played_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="recentplayerencounter",
            constraint=models.UniqueConstraint(
                fields=("user", "other_user"),
                name="unique_recent_player_pair",
            ),
        ),
        migrations.RunPython(backfill_recent_players, migrations.RunPython.noop),
    ]
