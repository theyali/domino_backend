from rest_framework import serializers

from .models import GameRoom, RoomPlayer


class RoomPlayerSerializer(serializers.ModelSerializer):
    active_gift = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = RoomPlayer
        fields = (
            "id",
            "user_id",
            "name",
            "avatar_url",
            "seat_index",
            "is_owner",
            "is_active",
            "is_online",
            "last_seen_at",
            "active_gift",
        )

    def get_avatar_url(self, obj):
        user = obj.user
        if user is None:
            return None

        profile = getattr(user, "profile", None)
        if profile is None or not profile.avatar:
            return None
        return profile.avatar.url

    def get_active_gift(self, obj):
        gift = obj.active_gift
        if gift is None:
            return None

        return {
            "id": gift.id,
            "restaurant_id": gift.restaurant_id,
            "name": gift.name,
            "image_url": gift.image.url if gift.image else None,
        }


class GameRoomSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    current_players = serializers.IntegerField(read_only=True)
    is_locked = serializers.BooleanField(source="has_password", read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    players = RoomPlayerSerializer(many=True, read_only=True)

    class Meta:
        model = GameRoom
        fields = (
            "id",
            "restaurant_id",
            "name",
            "display_name",
            "owner_name",
            "max_players",
            "current_players",
            "is_locked",
            "is_full",
            "status",
            "players",
            "created_at",
        )


class GameRoomCreateSerializer(serializers.Serializer):
    max_players = serializers.IntegerField(min_value=2, max_value=4)
    password = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        write_only=True,
    )
    name = serializers.CharField(
        max_length=80,
        required=False,
        allow_blank=True,
    )


class JoinRoomSerializer(serializers.Serializer):
    password = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        write_only=True,
    )


class LeaveRoomSerializer(serializers.Serializer):
    player_id = serializers.IntegerField(min_value=1)
