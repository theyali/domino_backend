from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from rooms.models import GameRoom, RoomPlayer

from .models import DirectMessage, Friendship, RoomInvitation, UserProfile


User = get_user_model()
ONLINE_TTL = timedelta(seconds=45)


def online_cutoff():
    return timezone.now() - ONLINE_TTL


def touch_presence(user):
    now = timezone.now()
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        profile.last_seen_at = now
        profile.save(update_fields=["last_seen_at"])
    else:
        UserProfile.objects.filter(pk=profile.pk).update(last_seen_at=now)
        profile.last_seen_at = now
    return profile


def _friendship_between(user, other_user):
    return (
        Friendship.objects.filter(
            Q(requester=user, addressee=other_user)
            | Q(requester=other_user, addressee=user)
        )
        .order_by("-created_at")
        .first()
    )


def friendship_state(user, other_user, friendship=None):
    friendship = friendship or _friendship_between(user, other_user)
    if friendship is None:
        return "none", None
    if friendship.status == Friendship.Status.ACCEPTED:
        return "friends", friendship.id
    if friendship.requester_id == user.id:
        return "outgoing", friendship.id
    return "incoming", friendship.id


def public_user_payload(user, viewer, *, friendship=None, last_played_at=None):
    profile = getattr(user, "profile", None)
    last_seen_at = getattr(profile, "last_seen_at", None)
    is_online = bool(last_seen_at and last_seen_at >= online_cutoff())
    relationship, friendship_id = friendship_state(viewer, user, friendship)
    full_name = (user.get_full_name() or "").strip()

    return {
        "id": user.id,
        "username": user.username,
        "display_name": full_name or user.username,
        "avatar_url": profile.avatar.url if profile and profile.avatar else None,
        "is_online": is_online,
        "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
        "friendship_status": relationship,
        "friendship_id": friendship_id,
        "last_played_at": last_played_at.isoformat() if last_played_at else None,
    }


def message_payload(message):
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "recipient_id": message.recipient_id,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
        "read_at": message.read_at.isoformat() if message.read_at else None,
    }


def invitation_payload(invitation, viewer):
    room = invitation.room
    restaurant = room.restaurant
    return {
        "id": invitation.id,
        "sender": public_user_payload(invitation.sender, viewer),
        "room_id": room.id,
        "room_name": room.display_name,
        "restaurant_id": restaurant.id,
        "restaurant_name": restaurant.name,
        "created_at": invitation.created_at.isoformat(),
        "status": invitation.status,
    }


def recent_players_for(user, *, limit=30):
    room_ids = list(
        RoomPlayer.objects.filter(user=user).values_list("room_id", flat=True).distinct()
    )
    if not room_ids:
        return []

    rows = (
        RoomPlayer.objects.filter(room_id__in=room_ids, user__isnull=False)
        .exclude(user=user)
        .select_related("user", "user__profile")
        .order_by("-joined_at", "-id")
    )
    seen = set()
    result = []
    for row in rows:
        other = row.user
        if other.id in seen:
            continue
        seen.add(other.id)
        result.append(
            public_user_payload(
                other,
                user,
                last_played_at=row.joined_at,
            )
        )
        if len(result) >= limit:
            break
    return result


def can_message(user, other_user):
    if user.id == other_user.id:
        return False

    friendship = _friendship_between(user, other_user)
    if friendship is not None and friendship.status == Friendship.Status.ACCEPTED:
        return True

    room_ids = RoomPlayer.objects.filter(user=user).values_list("room_id", flat=True)
    return RoomPlayer.objects.filter(
        room_id__in=room_ids,
        user=other_user,
    ).exists()


def social_overview(user):
    touch_presence(user)

    friendships = list(
        Friendship.objects.filter(
            Q(requester=user) | Q(addressee=user)
        ).select_related(
            "requester",
            "requester__profile",
            "addressee",
            "addressee__profile",
        )
    )

    friends = []
    incoming_requests = []
    for friendship in friendships:
        other = friendship.addressee if friendship.requester_id == user.id else friendship.requester
        if friendship.status == Friendship.Status.ACCEPTED:
            friends.append(public_user_payload(other, user, friendship=friendship))
        elif friendship.addressee_id == user.id:
            incoming_requests.append(
                {
                    "id": friendship.id,
                    "user": public_user_payload(other, user, friendship=friendship),
                    "created_at": friendship.created_at.isoformat(),
                }
            )

    unread_counts = {
        row["sender_id"]: row["count"]
        for row in DirectMessage.objects.filter(
            recipient=user,
            read_at__isnull=True,
        )
        .values("sender_id")
        .annotate(count=Count("id"))
    }

    conversations = []
    seen_partners = set()
    messages = (
        DirectMessage.objects.filter(Q(sender=user) | Q(recipient=user))
        .select_related(
            "sender",
            "sender__profile",
            "recipient",
            "recipient__profile",
        )
        .order_by("-created_at", "-id")
    )
    for message in messages:
        partner = message.recipient if message.sender_id == user.id else message.sender
        if partner.id in seen_partners:
            continue
        seen_partners.add(partner.id)
        conversations.append(
            {
                "user": public_user_payload(partner, user),
                "last_message": message.body,
                "last_message_at": message.created_at.isoformat(),
                "unread_count": unread_counts.get(partner.id, 0),
            }
        )
        if len(conversations) >= 30:
            break

    invitations = [
        invitation_payload(invitation, user)
        for invitation in RoomInvitation.objects.filter(
            recipient=user,
            status=RoomInvitation.Status.PENDING,
            room__status=GameRoom.Status.WAITING,
        )
        .select_related(
            "sender",
            "sender__profile",
            "room",
            "room__restaurant",
        )
        .order_by("-created_at")[:20]
    ]

    return {
        "friends": friends,
        "incoming_requests": incoming_requests,
        "recent_players": recent_players_for(user),
        "conversations": conversations,
        "invitations": invitations,
    }


def online_users_for(user, *, room_id=None, limit=100):
    touch_presence(user)
    queryset = (
        User.objects.filter(
            profile__last_seen_at__gte=online_cutoff(),
            is_active=True,
        )
        .exclude(pk=user.pk)
        .select_related("profile")
        .order_by("-profile__last_seen_at", "username")
    )

    if room_id is not None:
        current_room_user_ids = RoomPlayer.objects.filter(
            room_id=room_id,
            is_active=True,
            user__isnull=False,
        ).values_list("user_id", flat=True)
        queryset = queryset.exclude(pk__in=current_room_user_ids)

    return [public_user_payload(item, user) for item in queryset[:limit]]
