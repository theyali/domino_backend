from rest_framework import serializers

from .models import Gift, InventoryGift


class GiftSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)

    class Meta:
        model = Gift
        fields = (
            "id",
            "restaurant_id",
            "restaurant_name",
            "name",
            "price",
            "icon_url",
            "is_active",
        )


class InventoryGiftSerializer(serializers.ModelSerializer):
    gift = GiftSerializer(read_only=True)
    qr_code = serializers.CharField(read_only=True)

    class Meta:
        model = InventoryGift
        fields = (
            "id",
            "gift",
            "qr_code",
            "status",
            "acquired_at",
            "redeemed_at",
        )
