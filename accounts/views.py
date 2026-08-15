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

from .models import DirectMessage, Friendship, RoomInvitation, UserProfile
from .ranking import build_statistics_payload
from .serializers import (
    DirectMessageCreateSerializer,
    FriendRequestCreateSerializer,
    LoginSerializer,
    RegisterSerializer,
    RoomInvitationCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .social import (
    can_message,
    message_payload,
    online_cutoff,
    online_users_for,
    public_user_payload,
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

        friendship = (
            Friendship.objects.select_for_update()
            .filter(
                Q(requester=request.user, addressee=other)
                | Q(requester=other, addressee=request.user)
            )
            .first()
        )
        now = timezone.now()

        if friendship is None:
            friendship = Friendship.objects.create(
                requester=request.user,
                addressee=other,
            )
            response_status = status.HTTP_201_CREATED
        elif friendship.status == Friendship.Status.PENDING and friendship.addressee_id == request.user.id:
            # Если два человека одновременно хотят добавить друг друга,
            # второй запрос сразу превращает связь в дружбу.
            friendship.status = Friendship.Status.ACCEPTED
            friendship.accepted_at = now
            friendship.save(update_fields=["status", "accepted_at"])
            response_status = status.HTTP_200_OK
        else:
            response_status = status.HTTP_200_OK

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
            Friendship.objects.select_for_update().select_related(
                "requester", "requester__profile"
            ),
            pk=pk,
            addressee=request.user,
            status=Friendship.Status.PENDING,
        )
        friendship.status = Friendship.Status.ACCEPTED
        friendship.accepted_at = timezone.now()
        friendship.save(update_fields=["status", "accepted_at"])
        return Response(
            public_user_payload(
                friendship.requester,
                request.user,
                friendship=friendship,
            )
        )


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
        recipients = list(
            User.objects.filter(
                pk__in=requested_ids,
                is_active=True,
                profile__last_seen_at__gte=online_cutoff(),
            )
            .exclude(pk=request.user.pk)
            .exclude(pk__in=occupied_user_ids)
            .select_related("profile")
        )

        now = timezone.now()
        invitation_ids = []
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
                "room", "room__restaurant"
            ),
            pk=pk,
            recipient=request.user,
            status=RoomInvitation.Status.PENDING,
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
