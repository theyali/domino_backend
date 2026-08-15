from django.db import models

from rooms.models import GameRoom, RoomPlayer


class GameSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Идёт игра"
        ROUND_FINISHED = "round_finished", "Раунд завершён"
        FINISHED = "finished", "Матч завершён"

    room = models.OneToOneField(
        GameRoom,
        on_delete=models.CASCADE,
        related_name="game_session",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    round_number = models.PositiveSmallIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)
    consecutive_passes = models.PositiveSmallIntegerField(default=0)
    stats_recorded = models.BooleanField(default=False)

    current_player = models.ForeignKey(
        RoomPlayer,
        on_delete=models.CASCADE,
        related_name="current_turn_sessions",
    )
    opening_player = models.ForeignKey(
        RoomPlayer,
        on_delete=models.CASCADE,
        related_name="opening_sessions",
    )
    opening_domino_id = models.PositiveSmallIntegerField()

    hands = models.JSONField(default=dict)
    boneyard = models.JSONField(default=list)
    table = models.JSONField(default=list)
    scores = models.JSONField(default=dict)
    last_round_result = models.JSONField(default=dict, blank=True)

    turn_started_at = models.DateTimeField(null=True, blank=True)
    turn_deadline_at = models.DateTimeField(null=True, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Game #{self.pk} — {self.room.display_name}"
