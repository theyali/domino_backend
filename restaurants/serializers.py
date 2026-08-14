from rest_framework import serializers

from .models import Restaurant


class RestaurantSerializer(serializers.ModelSerializer):
    players = serializers.SerializerMethodField()
    active = serializers.BooleanField(source="is_active", read_only=True)
    waiting_rooms = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = (
            "id",
            "name",
            "players",
            "active",
            "waiting_rooms",
        )

    def get_players(self, obj):
        return sum(
            room.players.count()
            for room in obj.game_rooms.filter(status="waiting")
        )

    def get_waiting_rooms(self, obj):
        return obj.game_rooms.filter(status="waiting").count()
