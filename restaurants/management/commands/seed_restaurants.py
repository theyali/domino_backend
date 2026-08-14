from django.core.management.base import BaseCommand

from restaurants.models import Restaurant


RESTAURANTS = [
    ("Mangal Steak House", True),
    ("Dolma Restaurant", False),
    ("Nargiz", True),
    ("Chinar", False),
]


class Command(BaseCommand):
    help = "Create/update the initial restaurants used by the Flutter prototype."

    def handle(self, *args, **options):
        for name, is_active in RESTAURANTS:
            restaurant, created = Restaurant.objects.update_or_create(
                name=name,
                defaults={"is_active": is_active},
            )
            action = "created" if created else "updated"
            self.stdout.write(f"{restaurant.id}: {restaurant.name} ({action})")

        self.stdout.write(self.style.SUCCESS("Restaurants are ready."))
