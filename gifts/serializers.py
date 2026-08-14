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
            "acquired_at",
            "redeemed_at",
        )
