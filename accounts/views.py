from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.serializers import RestaurantSerializer
from rooms.models import GameRoom, RoomPlayer
from rooms.serializers import GameRoomSerializer, RoomPlayerSerializer
from rooms.services import join_room

from .models import (
    BlockedUser,
    DirectMessage,
    Friendship,
    PushDevice,
    RoomInvitation,
    UserProfile,
)
from .push import send_social_push
from .ranking import build_statistics_payload
from .serializers import (
    DirectMessageCreateSerializer,
    FriendRequestCreateSerializer,
    LoginSerializer,
    NotificationPreferencesSerializer,
    PushDeviceDeleteSerializer,
    PushDeviceSerializer,
    RegisterSerializer,
    RoomInvitationCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .social import (
    can_message,
    is_blocked_between,
    message_payload,
    online_cutoff,
    online_users_for,
    public_user_payload,
    search_users_for,
    social_overview,
    touch_presence,
)


User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        touch_presence(user)
        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        touch_presence(user)
        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        touch_presence(request.user)
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        touch_presence(user)
        return Response(UserSerializer(user).data)


class StatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        touch_presence(request.user)
        return Response(build_statistics_payload(request.user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        UserProfile.objects.filter(user=request.user).update(last_seen_at=None)
        PushDevice.objects.filter(user=request.user).update(is_active=False)
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SocialHeartbeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = touch_presence(request.user)
        return Response({"online": True, "last_seen_at": profile.last_seen_at})


class SocialOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(social_overview(request.user))


class SocialOnlineUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        room_id = request.query_params.get("room_id")
        if room_id is not None:
            try:
                room_id = int(room_id)
            except (TypeError, ValueError):
                room_id = None
        return Response(online_users_for(request.user, room_id=room_id))


class SocialUserSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        touch_presence(request.user)
        return Response(search_users_for(request.user, request.query_params.get("q", "")))


class SocialBlockedUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        touch_presence(request.user)
        rows = (
            BlockedUser.objects.filter(blocker=request.user)
            .select_related("blocked", "blocked__profile")
            .order_by("-created_at", "-id")
        )
        return Response(
            [public_user_payload(row.blocked, request.user) for row in rows]
        )


class SocialBlockUserView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, user_id):
        touch_presence(request.user)
        other = get_object_or_404(
            User.objects.select_related("profile"),
            pk=user_id,
            is_active=True,
        )
        if other.pk == request.user.pk:
            return Response(
                {"detail": "Нельзя заблокировать самого себя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        BlockedUser.objects.get_or_create(blocker=request.user, blocked=other)
        Friendship.objects.filter(
            Q(requester=request.user, addressee=other)
            | Q(requester=other, addressee=request.user)
        ).delete()
        RoomInvitation.objects.filter(
            Q(sender=request.user, recipient=other)
            | Q(sender=other, recipient=request.user),
            status=RoomInvitation.Status.PENDING,
        ).delete()

        return Response(public_user_payload(other, request.user))


class SocialUnblockUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        touch_presence(request.user)
        BlockedUser.objects.filter(
            blocker=request.user,
            blocked_id=user_id,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = touch_presence(request.user)
        return Response(NotificationPreferencesSerializer(profile).data)

    def patch(self, request):
        profile = touch_presence(request.user)
        serializer = NotificationPreferencesSerializer(
            profile,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PushDeviceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PushDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["registration_token"]
        platform = serializer.validated_data["platform"]
        now = timezone.now()

        # Один FCM registration token может принадлежать только одному
        # авторизованному аккаунту на устройстве.
        device, _ = PushDevice.objects.update_or_create(
            registration_token=token,
            defaults={
                "user": request.user,
                "platform": platform,
                "is_active": True,
                "last_seen_at": now,
            },
        )
        return Response(
            {
                "id": device.id,
                "platform": device.platform,
                "active": device.is_active,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        serializer = PushDeviceDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PushDevice.objects.filter(
            user=request.user,
            registration_token=serializer.validated_data["registration_token"],
        ).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        touch_presence(request.user)
        serializer = FriendRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        other = get_object_or_404(
            User.objects.select_related("profile"),
            pk=serializer.validated_data["user_id"],
            is_active=True,
        )
        if other.id == request.user.id:
            return Response(
                {"detail": "Нельзя добавить самого себя в друзья."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if is_blocked_between(request.user, other):
            return Response(
                {"detail": "Добавление в друзья недоступно для этого пользователя."},
                status=status.HTTP_403_FORBIDDEN,
            )

        friendship = (
            Friendship.objects.select_for_update()
            .filter(
                Q(requester=request.user, addressee=other)
                | Q(requester=other, addressee=request.user)
            )
            .first()
        )
        now = timezone.now()
        push_kind = None

        if friendship is None:
            friendship = Friendship.objects.create(
                requester=request.user,
                addressee=other,
            )
            response_status = status.HTTP_201_CREATED
            push_kind = "friend_request"
        elif (
            friendship.status == Friendship.Status.PENDING
            and friendship.addressee_id == request.user.id
        ):
            # Если два человека одновременно хотят добавить друг друга,
            # второй запрос сразу превращает связь в дружбу.
            friendship.status = Friendship.Status.ACCEPTED
            friendship.accepted_at = now
            friendship.save(update_fields=["status", "accepted_at"])
            response_status = status.HTTP_200_OK
            push_kind = "friend_accepted"
        else:
            response_status = status.HTTP_200_OK

        if push_kind == "friend_request":
            sender_name = (request.user.get_full_name() or request.user.username).strip()
            transaction.on_commit(
                lambda: send_social_push(
                    user=other,
                    kind="friend_request",
                    title="Новая заявка в друзья",
                    body=f"{sender_name} хочет добавить тебя в друзья.",
                    data={"user_id": request.user.id},
                ),
                robust=True,
            )
        elif push_kind == "friend_accepted":
            accepter_name = (request.user.get_full_name() or request.user.username).strip()
            transaction.on_commit(
                lambda: send_social_push(
                    user=other,
                    kind="friend_accepted",
                    title="Теперь вы друзья",
                    body=f"{accepter_name} принял твою заявку в друзья.",
                    data={"user_id": request.user.id},
                ),
                robust=True,
            )

        return Response(
            public_user_payload(other, request.user, friendship=friendship),
            status=response_status,
        )


class FriendRequestAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        touch_presence(request.user)
        friendship = get_object_or_404(
            Friendship.objects.select_for_update().select_related("requester"),
            pk=pk,
            addressee=request.user,
            status=Friendship.Status.PENDING,
        )
        if is_blocked_between(request.user, friendship.requester):
            return Response(
                {"detail": "Эта заявка больше недоступна."},
                status=status.HTTP_403_FORBIDDEN,
            )

        friendship.status = Friendship.Status.ACCEPTED
        friendship.accepted_at = timezone.now()
        friendship.save(update_fields=["status", "accepted_at"])

        accepter_name = (request.user.get_full_name() or request.user.username).strip()
        requester = friendship.requester
        transaction.on_commit(
            lambda: send_social_push(
                user=requester,
                kind="friend_accepted",
                title="Теперь вы друзья",
                body=f"{accepter_name} принял твою заявку в друзья.",
                data={"user_id": request.user.id},
            ),
            robust=True,
        )

        return Response(
            public_user_payload(
                friendship.requester,
                request.user,
                friendship=friendship,
            )
        )


class FriendRequestDeclineView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        touch_presence(request.user)
        friendship = get_object_or_404(
            Friendship.objects.select_for_update(),
            pk=pk,
            addressee=request.user,
            status=Friendship.Status.PENDING,
        )
        friendship.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendRequestCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        touch_presence(request.user)
        friendship = get_object_or_404(
            Friendship.objects.select_for_update(),
            pk=pk,
            requester=request.user,
            status=Friendship.Status.PENDING,
        )
        friendship.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendshipRemoveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        touch_presence(request.user)
        friendship = get_object_or_404(
            Friendship.objects.filter(
                Q(requester=request.user) | Q(addressee=request.user)
            ),
            pk=pk,
        )
        friendship.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DirectMessageThreadView(APIView):
    permission_classes = [IsAuthenticated]

    def _other_user(self, request, user_id):
        other = get_object_or_404(
            User.objects.select_related("profile"),
            pk=user_id,
            is_active=True,
        )
        if not can_message(request.user, other):
            return None
        return other

    def get(self, request, user_id):
        touch_presence(request.user)
        other = self._other_user(request, user_id)
        if other is None:
            return Response(
                {"detail": "Личные сообщения доступны друзьям и игрокам, с которыми вы играли."},
                status=status.HTTP_403_FORBIDDEN,
            )

        DirectMessage.objects.filter(
            sender=other,
            recipient=request.user,
            read_at__isnull=True,
        ).update(read_at=timezone.now())

        latest = list(
            DirectMessage.objects.filter(
                Q(sender=request.user, recipient=other)
                | Q(sender=other, recipient=request.user)
            )
            .order_by("-created_at", "-id")[:100]
        )
        latest.reverse()
        return Response(
            {
                "user": public_user_payload(other, request.user),
                "messages": [message_payload(item) for item in latest],
            }
        )

    def post(self, request, user_id):
        touch_presence(request.user)
        other = self._other_user(request, user_id)
        if other is None:
            return Response(
                {"detail": "Личные сообщения доступны друзьям и игрокам, с которыми вы играли."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DirectMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = DirectMessage.objects.create(
            sender=request.user,
            recipient=other,
            body=serializer.validated_data["body"],
        )

        sender_name = (request.user.get_full_name() or request.user.username).strip()
        preview = message.body if len(message.body) <= 120 else f"{message.body[:117]}..."
        transaction.on_commit(
            lambda: send_social_push(
                user=other,
                kind="direct_message",
                title=sender_name,
                body=preview,
                data={"user_id": request.user.id},
            )
        )
        return Response(message_payload(message), status=status.HTTP_201_CREATED)


class RoomInvitationCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, room_id):
        touch_presence(request.user)
        room = get_object_or_404(
            GameRoom.objects.select_for_update().select_related("restaurant"),
            pk=room_id,
        )
        if room.status != GameRoom.Status.WAITING:
            return Response(
                {"detail": "Приглашать игроков можно только до начала игры."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if room.is_full:
            return Response(
                {"detail": "За столом уже нет свободных мест."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not RoomPlayer.objects.filter(
            room=room,
            user=request.user,
            is_active=True,
        ).exists():
            return Response(
                {"detail": "Сначала нужно находиться за этим столом."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RoomInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_ids = serializer.validated_data["user_ids"]
        occupied_user_ids = set(
            RoomPlayer.objects.filter(
                room=room,
                is_active=True,
                user__isnull=False,
            ).values_list("user_id", flat=True)
        )
        blocked_user_ids = set(
            BlockedUser.objects.filter(blocker=request.user).values_list(
                "blocked_id", flat=True
            )
        )
        blocked_user_ids.update(
            BlockedUser.objects.filter(blocked=request.user).values_list(
                "blocker_id", flat=True
            )
        )

        recipients = list(
            User.objects.filter(
                pk__in=requested_ids,
                is_active=True,
                profile__last_seen_at__gte=online_cutoff(),
            )
            .exclude(pk=request.user.pk)
            .exclude(pk__in=occupied_user_ids)
            .exclude(pk__in=blocked_user_ids)
            .select_related("profile")
        )

        now = timezone.now()
        invitation_ids = []
        sender_name = (request.user.get_full_name() or request.user.username).strip()
        for recipient in recipients:
            invitation, created = RoomInvitation.objects.get_or_create(
                room=room,
                recipient=recipient,
                defaults={"sender": request.user},
            )
            if not created:
                invitation.sender = request.user
                invitation.status = RoomInvitation.Status.PENDING
                invitation.responded_at = None
                invitation.created_at = now
                invitation.save(
                    update_fields=[
                        "sender",
                        "status",
                        "responded_at",
                        "created_at",
                    ]
                )
            invitation_ids.append(invitation.id)

            invitation_id = invitation.id
            transaction.on_commit(
                lambda recipient=recipient, invitation_id=invitation_id: send_social_push(
                    user=recipient,
                    kind="room_invitation",
                    title="Приглашение за стол",
                    body=f"{sender_name} зовёт тебя в {room.restaurant.name} · {room.display_name}.",
                    data={
                        "invitation_id": invitation_id,
                        "room_id": room.id,
                        "restaurant_id": room.restaurant_id,
                    },
                )
            )

        return Response(
            {
                "sent": len(invitation_ids),
                "invitation_ids": invitation_ids,
            },
            status=status.HTTP_201_CREATED,
        )


class RoomInvitationAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        touch_presence(request.user)
        invitation = get_object_or_404(
            RoomInvitation.objects.select_for_update().select_related(
                "room", "room__restaurant", "sender"
            ),
            pk=pk,
            recipient=request.user,
            status=RoomInvitation.Status.PENDING,
        )
        if is_blocked_between(request.user, invitation.sender):
            return Response(
                {"detail": "Это приглашение больше недоступно."},
                status=status.HTTP_403_FORBIDDEN,
            )

        room, player = join_room(
            room_id=invitation.room_id,
            user=request.user,
            bypass_password=True,
        )
        invitation.status = RoomInvitation.Status.ACCEPTED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

        room.refresh_from_db()
        room = GameRoom.objects.select_related("restaurant").prefetch_related(
            "players", "players__user", "players__user__profile"
        ).get(pk=room.pk)
        player = room.players.get(pk=player.pk)

        return Response(
            {
                "restaurant": RestaurantSerializer(room.restaurant).data,
                "room": GameRoomSerializer(room).data,
                "player": RoomPlayerSerializer(player).data,
            }
        )


class RoomInvitationDeclineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        touch_presence(request.user)
        invitation = get_object_or_404(
            RoomInvitation,
            pk=pk,
            recipient=request.user,
            status=RoomInvitation.Status.PENDING,
        )
        invitation.status = RoomInvitation.Status.DECLINED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
