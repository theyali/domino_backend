from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from restaurants.models import Restaurant


class GameRoom(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Ожидание"
        PLAYING = "playing", "Игра"
        FINISHED = "finished", "Завершена"

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="game_rooms",
    )
    name = models.CharField(max_length=80, blank=True)
    owner_name = models.CharField(max_length=40)
    max_players = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2), MaxValueValidator(4)]
    )
    password_hash = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.WAITING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.name.strip() or f"Стол #{self.pk}"

    @property
    def has_password(self):
        return bool(self.password_hash)

    @property
    def current_players(self):
        return self.players.filter(is_active=True).count()

    @property
    def is_full(self):
        return self.current_players >= self.max_players

    def set_password(self, raw_password):
        raw_password = (raw_password or "").strip()
        self.password_hash = make_password(raw_password) if raw_password else ""

    def check_room_password(self, raw_password):
        if not self.has_password:
            return True
        return check_password(raw_password or "", self.password_hash)


class RoomPlayer(models.Model):
    room = models.ForeignKey(
        GameRoom,
        on_delete=models.CASCADE,
        related_name="players",
    )
    name = models.CharField(max_length=40)
    seat_index = models.PositiveSmallIntegerField()
    is_owner = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["seat_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "seat_index"],
                name="unique_room_seat",
            ),
        ]

    def __str__(self):
        return f"{self.name} @ {self.room.display_name}"
