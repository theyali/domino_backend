import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("restaurants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Gift",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("icon_url", models.URLField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "restaurant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gifts",
                        to="restaurants.restaurant",
                    ),
                ),
            ],
            options={"ordering": ["price", "id"]},
        ),
        migrations.CreateModel(
            name="InventoryGift",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "qr_token",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("available", "Доступен"),
                            ("redeemed", "Использован"),
                        ],
                        default="available",
                        max_length=16,
                    ),
                ),
                ("acquired_at", models.DateTimeField(auto_now_add=True)),
                ("redeemed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "gift",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="inventory_items",
                        to="gifts.gift",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_gifts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-acquired_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="gift",
            constraint=models.UniqueConstraint(
                fields=("restaurant", "name"),
                name="unique_gift_name_per_restaurant",
            ),
        ),
    ]
