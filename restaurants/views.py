from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import Restaurant
from .serializers import RestaurantSerializer


class RestaurantListView(ListAPIView):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    pagination_class = None


class RestaurantDetailView(RetrieveAPIView):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
