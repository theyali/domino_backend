from django.contrib import admin

from .models import Gift, InventoryGift


@admin.register(Gift)
class GiftAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "restaurant",
        "price",
        "is_active",
        "updated_at",
    )
    list_filter = ("restaurant", "is_active")
    search_fields = ("name", "restaurant__name")
    ordering = ("restaurant", "price", "id")


@admin.register(InventoryGift)
class InventoryGiftAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "gift",
        "owner",
        "status",
        "qr_token",
        "acquired_at",
        "redeemed_at",
    )
    list_filter = ("status", "gift__restaurant")
    search_fields = (
        "gift__name",
        "gift__restaurant__name",
        "owner__username",
        "owner__email",
        "qr_token",
    )
    readonly_fields = ("qr_token", "acquired_at")
    autocomplete_fields = ("owner", "gift")
