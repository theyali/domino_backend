from django.db.models import Count, Q
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
    PurchaseGiftSerializer,
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
        return (
            Gift.objects.filter(
                restaurant=restaurant,
                is_active=True,
            )
            .select_related("restaurant")
            .annotate(
                giftable_count=Count(
                    "inventory_items",
                    filter=Q(
                        inventory_items__owner=self.request.user,
                        inventory_items__status=InventoryGift.Status.AVAILABLE,
                        inventory_items__is_giftable=True,
                    ),
                )
            )
        )


class PurchaseGiftView(APIView):
    """Prototype purchase.

    Пока реальная платёжная система не подключена, endpoint просто создаёт
    giftable-экземпляры. Позже здесь будет создаваться InventoryGift только
    после подтверждения оплаты.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, restaurant_id, gift_id):
        restaurant = get_object_or_404(
            Restaurant,
            pk=restaurant_id,
            is_active=True,
        )
        gift = get_object_or_404(
            Gift,
            pk=gift_id,
            restaurant=restaurant,
            is_active=True,
        )
        serializer = PurchaseGiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data["quantity"]

        InventoryGift.objects.bulk_create(
            [
                InventoryGift(
                    owner=request.user,
                    gift=gift,
                    is_giftable=True,
                )
                for _ in range(quantity)
            ]
        )

        available_count = InventoryGift.objects.filter(
            owner=request.user,
            gift=gift,
            status=InventoryGift.Status.AVAILABLE,
            is_giftable=True,
        ).count()

        return Response(
            {
                "gift_id": gift.id,
                "added": quantity,
                "giftable_count": available_count,
            }
        )


class InventoryGiftListView(ListAPIView):
    serializer_class = InventoryGiftSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Главный «Инвентарь» — только подарки, полученные от других людей.
        # Купленные для последующего дарения экземпляры сюда не попадают.
        return (
            InventoryGift.objects.filter(
                owner=self.request.user,
                is_giftable=False,
            )
            .select_related(
                "gift",
                "gift__restaurant",
                "gifted_by",
            )
        )


class InventoryGiftDetailView(RetrieveAPIView):
    serializer_class = InventoryGiftSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            InventoryGift.objects.filter(
                owner=self.request.user,
                is_giftable=False,
            )
            .select_related(
                "gift",
                "gift__restaurant",
                "gifted_by",
            )
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
