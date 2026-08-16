from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Restaurant

from .models import Gift, GiftPurchase, InventoryGift
from .serializers import (
    GiftPurchaseSerializer,
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
                Q(restaurant=restaurant) | Q(restaurant__isnull=True),
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
            .order_by("level", "price", "id")
        )


class PurchaseGiftView(APIView):
    """Prototype purchase.

    Пока реальная платёжная система не подключена, endpoint создаёт
    giftable-экземпляры и записывает покупку в историю. После подключения
    оплаты обе записи должны создаваться только после подтверждения платежа.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, restaurant_id, gift_id):
        restaurant = get_object_or_404(
            Restaurant,
            pk=restaurant_id,
            is_active=True,
        )
        gift = get_object_or_404(
            Gift.objects.filter(
                Q(restaurant=restaurant) | Q(restaurant__isnull=True),
                is_active=True,
            ),
            pk=gift_id,
        )
        serializer = PurchaseGiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data["quantity"]

        with transaction.atomic():
            purchase = GiftPurchase.objects.create(
                purchaser=request.user,
                gift=gift,
                quantity=quantity,
                unit_price=gift.price,
            )
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
                "purchase_id": purchase.id,
                "added": quantity,
                "giftable_count": available_count,
                "total_price": f"{purchase.total_price:.2f}",
                "purchased_at": purchase.purchased_at.isoformat(),
            }
        )


class GiftPurchaseSummaryView(APIView):
    """История расходов и купленные подарки, которые ещё можно подарить."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        purchases = list(
            GiftPurchase.objects.filter(purchaser=request.user)
            .select_related("gift", "gift__restaurant")
            .order_by("-purchased_at", "-id")
        )
        total_spent = sum(
            (purchase.total_price for purchase in purchases),
            Decimal("0.00"),
        )

        owned_gifts = list(
            Gift.objects.filter(
                inventory_items__owner=request.user,
                inventory_items__status=InventoryGift.Status.AVAILABLE,
                inventory_items__is_giftable=True,
            )
            .select_related("restaurant")
            .annotate(
                giftable_count=Count(
                    "inventory_items",
                    filter=Q(
                        inventory_items__owner=request.user,
                        inventory_items__status=InventoryGift.Status.AVAILABLE,
                        inventory_items__is_giftable=True,
                    ),
                )
            )
            .filter(giftable_count__gt=0)
            .order_by("level", "restaurant__name", "price", "id")
        )
        available_count = sum(
            int(getattr(gift, "giftable_count", 0) or 0)
            for gift in owned_gifts
        )

        serializer_context = {"request": request}
        return Response(
            {
                "total_spent": f"{total_spent:.2f}",
                "available_count": available_count,
                "owned_gifts": GiftSerializer(
                    owned_gifts,
                    many=True,
                    context=serializer_context,
                ).data,
                "history": GiftPurchaseSerializer(
                    purchases,
                    many=True,
                    context=serializer_context,
                ).data,
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
