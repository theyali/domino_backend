from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "league_points",
        "games_played",
        "wins",
        "losses",
        "has_avatar",
    )
    search_fields = ("user__username", "user__email", "user__first_name")
    ordering = ("-league_points", "user__username")

    @admin.display(boolean=True, description="Аватар")
    def has_avatar(self, obj):
        return bool(obj.avatar)
