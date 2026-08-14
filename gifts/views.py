from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Restaurant

from .models import Gift, InventoryGift
from .serializers import (
    GiftSerializer,
    InventoryGiftSerializer,
    SendGiftSerializer,
)
from .services import send_gift_to_room_players


class RestaurantGiftListView(ListAPIView):
    serializer_class = GiftSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        restaurant = get_object_or_404(
            Restaurant,
            pk=self.kwargs["restaurant_id"],
            is_active=True,
        )
        return Gift.objects.filter(
            restaurant=restaurant,
            is_active=True,
        ).select_related("restaurant")


class InventoryGiftListView(ListAPIView):
    serializer_class = InventoryGiftSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            InventoryGift.objects.filter(owner=self.request.user)
            .select_related("gift", "gift__restaurant")
        )


class InventoryGiftDetailView(RetrieveAPIView):
    serializer_class = InventoryGiftSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            InventoryGift.objects.filter(owner=self.request.user)
            .select_related("gift", "gift__restaurant")
        )


class SendRoomGiftView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        serializer = SendGiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = send_gift_to_room_players(
            sender_user=request.user,
            room_id=room_id,
            gift_id=serializer.validated_data["gift_id"],
            recipient_player_ids=serializer.validated_data[
                "recipient_player_ids"
            ],
        )
        return Response(result)
