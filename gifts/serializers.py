from rest_framework import serializers

from .models import Gift, GiftPurchase, InventoryGift


class GiftSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.SerializerMethodField()
    is_global = serializers.BooleanField(read_only=True)
    image_url = serializers.SerializerMethodField()
    giftable_count = serializers.SerializerMethodField()

    class Meta:
        model = Gift
        fields = (
            "id",
            "restaurant_id",
            "restaurant_name",
            "is_global",
            "name",
            "price",
            "level",
            "image_url",
            "is_active",
            "giftable_count",
        )

    def get_restaurant_name(self, obj):
        if obj.restaurant_id is None:
            return None
        return obj.restaurant.name

    def get_image_url(self, obj):
        if not obj.image:
            return None

        request = self.context.get("request")
        if request is None:
            return obj.image.url

        return request.build_absolute_uri(obj.image.url)

    def get_giftable_count(self, obj):
        return int(getattr(obj, "giftable_count", 0) or 0)


class InventoryGiftSerializer(serializers.ModelSerializer):
    gift = GiftSerializer(read_only=True)
    qr_code = serializers.CharField(read_only=True)
    gifted_by_id = serializers.IntegerField(read_only=True)
    gifted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryGift
        fields = (
            "id",
            "gift",
            "qr_code",
            "status",
            "is_giftable",
            "gifted_by_id",
            "gifted_by_name",
            "gifted_at",
            "acquired_at",
            "redeemed_at",
        )

    def get_gifted_by_name(self, obj):
        sender = obj.gifted_by
        if sender is None:
            return None

        full_name = (sender.get_full_name() or "").strip()
        return full_name or sender.username


class GiftPurchaseSerializer(serializers.ModelSerializer):
    gift = GiftSerializer(read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = GiftPurchase
        fields = (
            "id",
            "gift",
            "quantity",
            "unit_price",
            "total_price",
            "purchased_at",
        )

    def get_total_price(self, obj):
        return f"{obj.total_price:.2f}"


class PurchaseGiftSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=20, default=1)


class SendGiftSerializer(serializers.Serializer):
    gift_id = serializers.IntegerField(min_value=1)
    recipient_player_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=4,
        allow_empty=False,
    )

    def validate_recipient_player_ids(self, value):
        unique_ids = list(dict.fromkeys(value))
        if len(unique_ids) != len(value):
            raise serializers.ValidationError("Получатели не должны повторяться.")
        return unique_ids
