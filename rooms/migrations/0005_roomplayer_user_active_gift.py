from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("gifts", "0002_replace_icon_url_with_image"),
        ("rooms", "0004_roomplayer_presence_connection_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="roomplayer",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="room_players",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="roomplayer",
            name="active_gift",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="active_room_players",
                to="gifts.gift",
            ),
        ),
    ]
