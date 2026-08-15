from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_purchase_history(apps, schema_editor):
    InventoryGift = apps.get_model("gifts", "InventoryGift")
    GiftPurchase = apps.get_model("gifts", "GiftPurchase")

    purchases = []
    items = InventoryGift.objects.select_related("gift").all().iterator()

    for item in items:
        purchaser_id = None
        if item.is_giftable:
            purchaser_id = item.owner_id
        elif item.gifted_by_id:
            purchaser_id = item.gifted_by_id

        if purchaser_id is None:
            continue

        purchases.append(
            GiftPurchase(
                purchaser_id=purchaser_id,
                gift_id=item.gift_id,
                quantity=1,
                unit_price=item.gift.price,
                purchased_at=item.acquired_at,
            )
        )

        if len(purchases) >= 500:
            GiftPurchase.objects.bulk_create(purchases)
            purchases.clear()

    if purchases:
        GiftPurchase.objects.bulk_create(purchases)


def clear_purchase_history(apps, schema_editor):
    GiftPurchase = apps.get_model("gifts", "GiftPurchase")
    GiftPurchase.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("gifts", "0004_inventorygift_gifted_by_gifted_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="GiftPurchase",
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
                ("quantity", models.PositiveSmallIntegerField(default=1)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "purchased_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "gift",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchases",
                        to="gifts.gift",
                    ),
                ),
                (
                    "purchaser",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gift_purchases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-purchased_at", "-id"],
            },
        ),
        migrations.RunPython(backfill_purchase_history, clear_purchase_history),
    ]
