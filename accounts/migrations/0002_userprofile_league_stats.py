from django.conf import settings
from django.db import migrations, models


def create_missing_profiles(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    UserProfile = apps.get_model("accounts", "UserProfile")

    existing_user_ids = set(
        UserProfile.objects.values_list("user_id", flat=True)
    )
    profiles = [
        UserProfile(user_id=user_id)
        for user_id in User.objects.values_list("id", flat=True)
        if user_id not in existing_user_ids
    ]
    if profiles:
        UserProfile.objects.bulk_create(profiles)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="games_played",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="league_points",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="losses",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="wins",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(create_missing_profiles, migrations.RunPython.noop),
    ]
