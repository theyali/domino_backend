from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Restaurant

from .models import GameRoom
from .presence import cleanup_stale_rooms
from .serializers import (
    GameRoomCreateSerializer,
    GameRoomSerializer,
    JoinRoomSerializer,
    LeaveRoomSerializer,
    RoomPlayerSerializer,
)
from .services import create_room, join_room, leave_room


class RestaurantRoomsView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request, restaurant_id):
        restaurant = get_object_or_404(Restaurant, pk=restaurant_id)

        cleanup_stale_rooms(restaurant_id=restaurant_id)

        rooms = (
            restaurant.game_rooms.filter(status=GameRoom.Status.WAITING)
            .prefetch_related("players")
            .order_by("-created_at")
        )
        return Response(GameRoomSerializer(rooms, many=True).data)

    def post(self, request, restaurant_id):
        restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
        serializer = GameRoomCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        room = create_room(
            restaurant=restaurant,
            owner_name=serializer.validated_data["owner_name"],
            max_players=serializer.validated_data["max_players"],
            password=serializer.validated_data.get("password", ""),
            name=serializer.validated_data.get("name", ""),
            user=request.user,
        )
        room = GameRoom.objects.prefetch_related("players").get(pk=room.pk)
        return Response(
            GameRoomSerializer(room).data,
            status=status.HTTP_201_CREATED,
        )


class RoomDetailView(APIView):
    def get(self, request, room_id):
        room = get_object_or_404(
            GameRoom.objects.prefetch_related("players"),
            pk=room_id,
        )
        return Response(GameRoomSerializer(room).data)


class JoinRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        serializer = JoinRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        room, player = join_room(
            room_id=room_id,
            player_name=serializer.validated_data["player_name"],
            password=serializer.validated_data.get("password", ""),
            user=request.user,
        )
        room = GameRoom.objects.prefetch_related("players").get(pk=room.pk)

        return Response(
            {
                "room": GameRoomSerializer(room).data,
                "player": RoomPlayerSerializer(player).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LeaveRoomView(APIView):
    def post(self, request, room_id):
        serializer = LeaveRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = leave_room(
            room_id=room_id,
            player_id=serializer.validated_data["player_id"],
        )
        return Response(result)
