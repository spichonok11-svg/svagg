from django.urls import path, re_path

from . import views

urlpatterns = [
    path("api/auth/session", views.auth_session, name="auth-session"),
    path("api/auth/register", views.auth_register, name="auth-register"),
    path("api/auth/login", views.auth_login, name="auth-login"),
    path("api/auth/logout", views.auth_logout, name="auth-logout"),
    path("api/health", views.health, name="health"),
    path("api/stats", views.stats, name="stats"),
    path("api/categories", views.categories, name="categories"),
    path("api/price-options", views.price_options, name="price-options"),
    path("api/cities", views.cities, name="cities"),
    path("api/search-suggestions", views.search_suggestions, name="search-suggestions"),
    path("api/reviews", views.reviews, name="reviews"),
    path("api/tours", views.tours, name="tours"),
    path("api/parse", views.parse, name="parse"),
    path("", views.index, name="index"),
    re_path(r"^(?!(api|static)/).*$", views.index, name="spa-fallback"),
]
