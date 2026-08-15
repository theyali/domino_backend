from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # Регистрируем lifecycle-хуки социальных данных после загрузки приложений.
        from . import signals  # noqa: F401
