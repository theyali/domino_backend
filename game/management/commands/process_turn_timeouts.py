from django.core.management.base import BaseCommand

from game.turn_timeout import process_all_expired_turns


class Command(BaseCommand):
    help = "Обрабатывает просроченные ходы активных игр."

    def handle(self, *args, **options):
        processed = process_all_expired_turns()
        self.stdout.write(
            self.style.SUCCESS(
                f"Обработано просроченных ходов: {processed}"
            )
        )
