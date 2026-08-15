from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restaurants", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurant",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="restaurants/",
            ),
        ),
    ]
