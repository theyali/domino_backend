from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("gifts", "0005_giftpurchase"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="gift",
            options={"ordering": ["level", "price", "id"]},
        ),
        migrations.AlterField(
            model_name="gift",
            name="restaurant",
            field=models.ForeignKey(
                blank=True,
                help_text="Оставь пустым, чтобы подарок был доступен во всех ресторанах.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="gifts",
                to="restaurants.restaurant",
            ),
        ),
        migrations.AddField(
            model_name="gift",
            name="level",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Уровень ценности подарка: от 1 до 5.",
                validators=[MinValueValidator(1), MaxValueValidator(5)],
            ),
        ),
        migrations.AddConstraint(
            model_name="gift",
            constraint=models.UniqueConstraint(
                condition=models.Q(("restaurant__isnull", True)),
                fields=("name",),
                name="unique_global_gift_name",
            ),
        ),
    ]
