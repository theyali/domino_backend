from datetime import timedelta

from django.utils import timezone

TURN_SECONDS = 30


def reset_turn_clock(session, *, now=None):
    started_at = now or timezone.now()
    session.turn_started_at = started_at
    session.turn_deadline_at = started_at + timedelta(seconds=TURN_SECONDS)


def clear_turn_clock(session):
    session.turn_started_at = None
    session.turn_deadline_at = None
