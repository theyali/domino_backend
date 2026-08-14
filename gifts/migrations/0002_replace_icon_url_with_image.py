from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gifts", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="gift",
            name="icon_url",
        ),
        migrations.AddField(
            model_name="gift",
            name="image",
            field=models.ImageField(blank=True, upload_to="gifts/"),
        ),
    ]
