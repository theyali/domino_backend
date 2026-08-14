from rest_framework import serializers

from .models import Gift, InventoryGift


class GiftSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Gift
        fields = (
            "id",
            "restaurant_id",
            "restaurant_name",
            "name",
            "price",
            "image_url",
            "is_active",
        )

    def get_image_url(self, obj):
        if not obj.image:
            return None

        request = self.context.get("request")
        if request is None:
            return obj.image.url

        return request.build_absolute_uri(obj.image.url)


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
            "is_giftable",
            "acquired_at",
            "redeemed_at",
        )


class SendGiftSerializer(serializers.Serializer):
    gift_id = serializers.IntegerField(min_value=1)
    recipient_player_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=3,
        allow_empty=False,
    )

    def validate_recipient_player_ids(self, value):
        unique_ids = list(dict.fromkeys(value))
        if len(unique_ids) != len(value):
            raise serializers.ValidationError("Получатели не должны повторяться.")
        return unique_ids
