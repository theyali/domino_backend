from rest_framework import serializers

from .models import Restaurant


class RestaurantSerializer(serializers.ModelSerializer):
    players = serializers.SerializerMethodField()
    active = serializers.BooleanField(source="is_active", read_only=True)
    waiting_rooms = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = (
            "id",
            "name",
            "image_url",
            "players",
            "active",
            "waiting_rooms",
        )

    def get_image_url(self, obj):
        if not obj.image:
            return None
        return obj.image.url

    def get_players(self, obj):
        return sum(
            room.players.filter(is_active=True).count()
            for room in obj.game_rooms.filter(status="waiting")
        )

    def get_waiting_rooms(self, obj):
        return obj.game_rooms.filter(status="waiting").count()
