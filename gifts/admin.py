from django.contrib import admin
from django.utils.html import format_html

from .models import Gift, InventoryGift


@admin.register(Gift)
class GiftAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "restaurant",
        "price",
        "image_preview",
        "is_active",
        "updated_at",
    )
    list_filter = ("restaurant", "is_active")
    search_fields = ("name", "restaurant__name")
    ordering = ("restaurant", "price", "id")
    readonly_fields = ("image_preview",)

    @admin.display(description="Изображение")
    def image_preview(self, obj):
        if not obj or not obj.image:
            return "—"

        return format_html(
            '<img src="{}" style="width: 72px; height: 72px; '
            'object-fit: contain; border-radius: 12px;" />',
            obj.image.url,
        )


@admin.register(InventoryGift)
class InventoryGiftAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "gift",
        "owner",
        "status",
        "is_giftable",
        "qr_token",
        "acquired_at",
        "redeemed_at",
    )
    list_filter = ("status", "is_giftable", "gift__restaurant")
    search_fields = (
        "gift__name",
        "gift__restaurant__name",
        "owner__username",
        "owner__email",
        "qr_token",
    )
    readonly_fields = ("qr_token", "acquired_at")
    autocomplete_fields = ("owner", "gift")
