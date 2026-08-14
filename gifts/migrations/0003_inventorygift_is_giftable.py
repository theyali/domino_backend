from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gifts", "0002_replace_icon_url_with_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventorygift",
            name="is_giftable",
            field=models.BooleanField(default=True),
        ),
    ]
