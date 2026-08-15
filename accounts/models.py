from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
    )
    league_points = models.PositiveIntegerField(default=0)
    games_played = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    # Глобальный presence для друзей/приглашений. Flutter присылает heartbeat,
    # поэтому отдельное постоянное is_online поле не нужно: online вычисляется
    # по свежести last_seen_at и само протухает, если приложение закрыто.
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Push-настройки хранятся на сервере, чтобы они одинаково работали на
    # нескольких устройствах пользователя.
    push_notifications_enabled = models.BooleanField(default=True)
    notify_friend_requests = models.BooleanField(default=True)
    notify_room_invites = models.BooleanField(default=True)
    notify_direct_messages = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile #{self.pk} — {self.user_id}"


class Friendship(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        ACCEPTED = "accepted", "Друзья"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_friendships",
    )
    addressee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_friendships",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "addressee"],
                name="unique_friendship_direction",
            ),
        ]

    def __str__(self):
        return f"{self.requester_id} → {self.addressee_id} ({self.status})"


class BlockedUser(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_users",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_by_users",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="unique_blocked_user_pair",
            ),
        ]

    def __str__(self):
        return f"{self.blocker_id} blocked {self.blocked_id}"


class RecentPlayerEncounter(models.Model):
    """Постоянная история людей, с которыми пользователь реально начал матч."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recent_player_encounters",
    )
    other_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recent_opponent_encounters",
    )
    last_played_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_played_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "other_user"],
                name="unique_recent_player_pair",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} played with {self.other_user_id}"


class DirectMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_direct_messages",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_direct_messages",
    )
    body = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["sender", "recipient", "created_at"],
                name="dm_sender_recipient_idx",
            ),
            models.Index(
                fields=["recipient", "sender", "created_at"],
                name="dm_recipient_sender_idx",
            ),
        ]

    def __str__(self):
        return f"DM #{self.pk}: {self.sender_id} → {self.recipient_id}"


class PushDevice(models.Model):
    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_devices",
    )
    registration_token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=16, choices=Platform.choices)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-last_seen_at", "-id"]

    def __str__(self):
        return f"PushDevice #{self.pk} — {self.user_id} ({self.platform})"


class RoomInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        ACCEPTED = "accepted", "Принято"
        DECLINED = "declined", "Отклонено"

    room = models.ForeignKey(
        "rooms.GameRoom",
        on_delete=models.CASCADE,
        related_name="social_invitations",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_room_invitations",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_room_invitations",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "recipient"],
                name="unique_room_invite_recipient",
            ),
        ]

    def __str__(self):
        return f"Invite #{self.pk}: room {self.room_id} → {self.recipient_id}"
