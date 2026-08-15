from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from rooms.models import GameRoom, RoomPlayer

from .models import PushDevice, UserProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "avatar_url")

    def get_avatar_url(self, obj):
        profile = getattr(obj, "profile", None)
        if profile is None or not profile.avatar:
            return None
        return profile.avatar.url


class UserUpdateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "avatar")
        extra_kwargs = {
            "username": {"required": True},
            "email": {"required": True},
            "first_name": {"required": True, "allow_blank": False},
        }

    def validate_username(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Введите имя пользователя.")

        queryset = User.objects.filter(username__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Это имя пользователя уже занято.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError("Введите email.")

        queryset = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        return value

    def validate_first_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Введите отображаемое имя.")
        return value[:40]

    def validate_avatar(self, value):
        if value is None:
            return value
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Аватар должен быть не больше 5 МБ.")
        return value

    def update(self, instance, validated_data):
        avatar_was_provided = "avatar" in validated_data
        avatar = validated_data.pop("avatar", None)

        instance.username = validated_data.get("username", instance.username)
        instance.email = validated_data.get("email", instance.email)
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.save(update_fields=["username", "email", "first_name"])

        if avatar_was_provided:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            if profile.avatar:
                profile.avatar.delete(save=False)
            profile.avatar = avatar
            profile.save()

        display_name = (instance.get_full_name() or instance.username).strip()[:40]
        active_players = RoomPlayer.objects.filter(
            user=instance,
            is_active=True,
        )
        owned_room_ids = list(
            active_players.filter(is_owner=True).values_list("room_id", flat=True)
        )
        active_players.update(name=display_name)
        if owned_room_ids:
            GameRoom.objects.filter(pk__in=owned_room_ids).update(
                owner_name=display_name,
            )

        return instance


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Введите имя пользователя.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Это имя пользователя уже занято.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Пароли не совпадают."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        username = validated_data["username"]
        user = User(
            username=username,
            email=validated_data["email"],
            first_name=username,
        )
        user.set_password(password)
        user.save()
        UserProfile.objects.get_or_create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs["username"].strip(),
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError(
                {"detail": "Неверное имя пользователя или пароль."}
            )
        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "Этот аккаунт отключён."}
            )
        attrs["user"] = user
        return attrs


class FriendRequestCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)


class DirectMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Сообщение не может быть пустым.")
        return value


class RoomInvitationCreateSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        min_length=1,
        max_length=100,
    )

    def validate_user_ids(self, value):
        return list(dict.fromkeys(value))


class NotificationPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = (
            "push_notifications_enabled",
            "notify_friend_requests",
            "notify_room_invites",
            "notify_direct_messages",
        )


class PushDeviceSerializer(serializers.Serializer):
    registration_token = serializers.CharField(max_length=512)
    platform = serializers.ChoiceField(choices=PushDevice.Platform.choices)

    def validate_registration_token(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Пустой push token.")
        return value


class PushDeviceDeleteSerializer(serializers.Serializer):
    registration_token = serializers.CharField(max_length=512)
