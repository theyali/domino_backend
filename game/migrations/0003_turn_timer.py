from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


TURN_SECONDS = 30


def initialize_active_turn_timers(apps, schema_editor):
    GameSession = apps.get_model("game", "GameSession")
    started_at = timezone.now()
    deadline_at = started_at + timedelta(seconds=TURN_SECONDS)

    GameSession.objects.filter(
        status="active",
        turn_deadline_at__isnull=True,
    ).update(
        turn_started_at=started_at,
        turn_deadline_at=deadline_at,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0002_round_results"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="turn_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gamesession",
            name="turn_deadline_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            initialize_active_turn_timers,
            migrations.RunPython.noop,
        ),
    ]
