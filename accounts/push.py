import logging
import os

from django.utils import timezone

from .models import PushDevice, UserProfile

logger = logging.getLogger(__name__)


def _firebase_messaging():
    """Ленивая инициализация Firebase: локальная разработка не должна падать без ключей."""
    try:
        import firebase_admin
        from firebase_admin import messaging
    except ImportError:
        return None

    try:
        firebase_admin.get_app()
    except ValueError:
        project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
        options = {"projectId": project_id} if project_id else None
        try:
            firebase_admin.initialize_app(options=options)
        except Exception:
            logger.exception("Firebase Admin is not configured; push notifications are disabled.")
            return None

    return messaging


def _notification_allowed(profile, kind):
    if not profile.push_notifications_enabled:
        return False
    if kind in {"friend_request", "friend_accepted"}:
        return profile.notify_friend_requests
    if kind == "room_invitation":
        return profile.notify_room_invites
    if kind == "direct_message":
        return profile.notify_direct_messages
    return True


def send_social_push(*, user, kind, title, body, data=None):
    """Отправляет push на все активные устройства пользователя и никогда не ломает API."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not _notification_allowed(profile, kind):
        return 0

    messaging = _firebase_messaging()
    if messaging is None:
        return 0

    devices = list(
        PushDevice.objects.filter(user=user, is_active=True).order_by("-last_seen_at")
    )
    if not devices:
        return 0

    payload = {"type": str(kind)}
    for key, value in (data or {}).items():
        if value is not None:
            payload[str(key)] = str(value)

    sent = 0
    for device in devices:
        try:
            message = messaging.Message(
                token=device.registration_token,
                notification=messaging.Notification(title=title, body=body),
                data=payload,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(sound="default"),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default", badge=1),
                    ),
                ),
            )
            messaging.send(message)
            sent += 1
            PushDevice.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
        except Exception as error:
            # Просроченные FCM/APNs registration tokens больше не используем.
            error_name = error.__class__.__name__
            if error_name in {
                "UnregisteredError",
                "SenderIdMismatchError",
                "InvalidArgumentError",
            }:
                PushDevice.objects.filter(pk=device.pk).update(is_active=False)
            else:
                logger.exception("Failed to send push to device %s", device.pk)

    return sent
