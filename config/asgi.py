import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize Django before importing routing that can touch app modules.
django_asgi_app = get_asgi_application()

from rooms.routing import websocket_urlpatterns  # noqa: E402


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(websocket_urlpatterns),
    }
)
