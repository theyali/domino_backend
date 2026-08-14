from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    return JsonResponse({"status": "ok", "service": "domino_backend"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/", include("accounts.urls")),
    path("api/", include("restaurants.urls")),
    path("api/", include("rooms.urls")),
    path("api/", include("game.urls")),
    path("api/", include("gifts.urls")),
]
