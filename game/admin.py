from django.contrib import admin

from .models import GameSession


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room",
        "status",
        "round_number",
        "current_player",
        "started_at",
    )
    list_filter = ("status",)
    readonly_fields = ("started_at", "updated_at")
