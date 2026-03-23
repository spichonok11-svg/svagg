from django.urls import path, re_path

from . import views

urlpatterns = [
    path("api/health", views.health, name="health"),
    path("api/stats", views.stats, name="stats"),
    path("api/categories", views.categories, name="categories"),
    path("api/price-options", views.price_options, name="price-options"),
    path("api/cities", views.cities, name="cities"),
    path("api/tours", views.tours, name="tours"),
    path("api/parse", views.parse, name="parse"),
    path("", views.index, name="index"),
    re_path(r"^(?!api/).*$", views.index, name="spa-fallback"),
]
