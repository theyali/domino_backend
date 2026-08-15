from django.db.models.signals import post_save
from django.dispatch import receiver

from game.models import GameSession

from .social import record_recent_players


@receiver(post_save, sender=GameSession)
def remember_match_opponents(sender, instance, created, **kwargs):
    if not created:
        return

    players = list(
        instance.room.players.filter(
            is_active=True,
            user__isnull=False,
        ).select_related("user")
    )
    record_recent_players(players)
