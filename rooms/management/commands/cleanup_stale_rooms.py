from django.core.management.base import BaseCommand, CommandError

from rooms.presence import DEFAULT_STALE_ROOM_MINUTES, cleanup_stale_rooms


class Command(BaseCommand):
    help = "Удаляет комнаты, в которых давно не было активных игроков."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=DEFAULT_STALE_ROOM_MINUTES,
            help=(
                "Удалять комнаты, если ни один активный игрок не был виден "
                "столько минут. По умолчанию: %(default)s."
            ),
        )

    def handle(self, *args, **options):
        minutes = options["minutes"]
        if minutes <= 0:
            raise CommandError("--minutes должен быть больше 0.")

        deleted_room_ids = cleanup_stale_rooms(minutes=minutes)

        if not deleted_room_ids:
            self.stdout.write(self.style.SUCCESS("Забытых комнат не найдено."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Удалено комнат: {len(deleted_room_ids)}. "
                f"ID: {', '.join(str(room_id) for room_id in deleted_room_ids)}"
            )
        )
