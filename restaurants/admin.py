from django.contrib import admin

from .models import Restaurant


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "has_image", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)

    @admin.display(boolean=True, description="Логотип")
    def has_image(self, obj):
        return bool(obj.image)
