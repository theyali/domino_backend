from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_blocks_push_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[
                    ("male", "Мужской"),
                    ("female", "Женский"),
                ],
                default="",
                max_length=8,
            ),
        ),
    ]
