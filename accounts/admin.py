from django.contrib import admin

from .models import (
    BlockedUser,
    DirectMessage,
    Friendship,
    PushDevice,
    RecentPlayerEncounter,
    RoomInvitation,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "league_points",
        "games_played",
        "wins",
        "losses",
        "push_notifications_enabled",
        "last_seen_at",
        "has_avatar",
    )
    list_filter = (
        "push_notifications_enabled",
        "notify_friend_requests",
        "notify_room_invites",
        "notify_direct_messages",
    )
    search_fields = ("user__username", "user__email", "user__first_name")
    ordering = ("-league_points", "user__username")

    @admin.display(boolean=True, description="Аватар")
    def has_avatar(self, obj):
        return bool(obj.avatar)


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("id", "requester", "addressee", "status", "created_at", "accepted_at")
    list_filter = ("status",)
    search_fields = (
        "requester__username",
        "requester__email",
        "addressee__username",
        "addressee__email",
    )
    autocomplete_fields = ("requester", "addressee")


@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    list_display = ("id", "blocker", "blocked", "created_at")
    search_fields = ("blocker__username", "blocked__username")
    autocomplete_fields = ("blocker", "blocked")
    ordering = ("-created_at",)


@admin.register(RecentPlayerEncounter)
class RecentPlayerEncounterAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "other_user", "last_played_at")
    search_fields = (
        "user__username",
        "user__email",
        "other_user__username",
        "other_user__email",
    )
    autocomplete_fields = ("user", "other_user")
    ordering = ("-last_played_at",)


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "recipient", "short_body", "created_at", "read_at")
    search_fields = ("sender__username", "recipient__username", "body")
    autocomplete_fields = ("sender", "recipient")
    readonly_fields = ("created_at", "read_at")

    @admin.display(description="Сообщение")
    def short_body(self, obj):
        return obj.body[:80]


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "platform", "is_active", "last_seen_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__username", "registration_token")
    readonly_fields = ("created_at", "last_seen_at")


@admin.register(RoomInvitation)
class RoomInvitationAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "sender", "recipient", "status", "created_at", "responded_at")
    list_filter = ("status", "room__restaurant")
    search_fields = (
        "room__name",
        "room__restaurant__name",
        "sender__username",
        "recipient__username",
    )
    autocomplete_fields = ("room", "sender", "recipient")
    readonly_fields = ("created_at", "responded_at")
