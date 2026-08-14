from django.contrib import admin

from .models import GameRoom, RoomPlayer


class RoomPlayerInline(admin.TabularInline):
    model = RoomPlayer
    extra = 0
    readonly_fields = ("joined_at",)


@admin.register(GameRoom)
class GameRoomAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurant",
        "display_name",
        "owner_name",
        "status",
        "max_players",
        "current_players",
        "has_password",
        "created_at",
    )
    list_filter = ("status", "restaurant", "max_players")
    search_fields = ("name", "owner_name", "restaurant__name")
    inlines = (RoomPlayerInline,)


@admin.register(RoomPlayer)
class RoomPlayerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "room", "seat_index", "is_owner", "joined_at")
    list_filter = ("is_owner",)
    search_fields = ("name", "room__name", "room__owner_name")
