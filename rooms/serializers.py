from rest_framework import serializers

from .models import GameRoom, RoomPlayer


class RoomPlayerSerializer(serializers.ModelSerializer):
    active_gift = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()

    class Meta:
        model = RoomPlayer
        fields = (
            "id",
            "user_id",
            "name",
            "avatar_url",
            "gender",
            "seat_index",
            "is_owner",
            "is_bot",
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

    def get_gender(self, obj):
        user = obj.user
        if user is None:
            return ""
        profile = getattr(user, "profile", None)
        return profile.gender if profile is not None else ""

    def get_active_gift(self, obj):
        gift = obj.active_gift
        if gift is None:
            return None

        return {
            "id": gift.id,
            "restaurant_id": gift.restaurant_id,
            "is_global": gift.is_global,
            "name": gift.name,
            "level": gift.level,
            "image_url": gift.image.url if gift.image else None,
        }


class GameRoomSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    game_mode_label = serializers.CharField(read_only=True)
    current_players = serializers.IntegerField(read_only=True)
    is_locked = serializers.BooleanField(source="has_password", read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    bot_count = serializers.SerializerMethodField()
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
            "game_mode",
            "game_mode_label",
            "target_score",
            "current_players",
            "bot_count",
            "is_locked",
            "is_full",
            "status",
            "players",
            "created_at",
        )


    def get_bot_count(self, obj):
        return obj.players.filter(is_active=True, is_bot=True).count()


class GameRoomCreateSerializer(serializers.Serializer):
    max_players = serializers.IntegerField(min_value=2, max_value=4)
    bot_count = serializers.IntegerField(min_value=0, max_value=3, default=0)
    game_mode = serializers.ChoiceField(
        choices=GameRoom.GameMode.choices,
        default=GameRoom.GameMode.CLASSIC_101,
    )
    target_score = serializers.IntegerField(
        min_value=5,
        max_value=500,
        required=False,
    )
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

    def validate(self, attrs):
        game_mode = attrs.get("game_mode", GameRoom.GameMode.CLASSIC_101)
        max_players = attrs["max_players"]
        bot_count = attrs.get("bot_count", 0)

        if bot_count > max_players - 1:
            raise serializers.ValidationError(
                {"bot_count": "Количество ботов должно оставлять место создателю комнаты."}
            )

        if game_mode == GameRoom.GameMode.CLASSIC_101:
            if max_players != 2:
                raise serializers.ValidationError(
                    {"max_players": "Для правила 101 нужен стол на 2 игроков."}
                )
            attrs["target_score"] = 101
            return attrs

        attrs["target_score"] = attrs.get("target_score", 72)
        return attrs


class JoinRoomSerializer(serializers.Serializer):
    password = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        write_only=True,
    )


class LeaveRoomSerializer(serializers.Serializer):
    player_id = serializers.IntegerField(min_value=1)
