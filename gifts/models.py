from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from restaurants.models import Restaurant


class Gift(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="gifts",
    )
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(
        upload_to="gifts/",
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "name"],
                name="unique_gift_name_per_restaurant",
            ),
        ]

    def __str__(self):
        return f"{self.name} — {self.restaurant.name}"


class GiftPurchase(models.Model):
    """История покупок подарков пользователем.

    Цена хранится снимком на момент покупки, поэтому изменение цены Gift
    позже не переписывает историю расходов пользователя.
    """

    purchaser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gift_purchases",
    )
    gift = models.ForeignKey(
        Gift,
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchased_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-purchased_at", "-id"]

    @property
    def total_price(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return (
            f"{self.purchaser.username}: {self.gift.name} "
            f"× {self.quantity}"
        )


class InventoryGift(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Доступен"
        REDEEMED = "redeemed", "Использован"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_gifts",
    )
    gift = models.ForeignKey(
        Gift,
        on_delete=models.PROTECT,
        related_name="inventory_items",
    )
    qr_token = models.UUIDField(default=uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    # True = куплен/выдан самому пользователю для последующего дарения.
    # False = уже получен от другого пользователя и передаривать его нельзя.
    is_giftable = models.BooleanField(default=True)
    gifted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sent_inventory_gifts",
        null=True,
        blank=True,
    )
    gifted_at = models.DateTimeField(null=True, blank=True)
    acquired_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-acquired_at", "-id"]

    @property
    def qr_code(self):
        return f"domino-gift://redeem/{self.qr_token}"

    def __str__(self):
        return f"{self.gift.name} → {self.owner.username}"
