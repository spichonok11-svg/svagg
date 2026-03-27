"""
Django settings for config project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-bsg)a0*bnb@od9_#o3p_*et05o8(9768a1tb2&v2c^kna7*4+8"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tours",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PROJECT_ROOT / "frontend"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "/static/"
STATICFILES_DIRS = [PROJECT_ROOT / "frontend"]

GO_PARSER_URL = os.getenv("GO_PARSER_URL", "http://127.0.0.1:8090/parse")
TOUR_CACHE_TTL_SECONDS = int(os.getenv("TOUR_CACHE_TTL_SECONDS", "300"))
LIVE_PARSER_ENABLED = os.getenv("LIVE_PARSER_ENABLED", "1") == "1"
PUTEVKA_SITEMAP_ENABLED = os.getenv("PUTEVKA_SITEMAP_ENABLED", "1") == "1"
PUTEVKA_REGIONS_SITEMAP_URL = os.getenv(
    "PUTEVKA_REGIONS_SITEMAP_URL",
    "https://www.putevka.com/sitemaps/regions.xml",
)
PUTEVKA_SITEMAP_REGIONS_LIMIT = int(os.getenv("PUTEVKA_SITEMAP_REGIONS_LIMIT", "30000"))
PUTEVKA_MIN_TOURS_TARGET = int(os.getenv("PUTEVKA_MIN_TOURS_TARGET", "100000"))
PUTEVKA_REGION_BATCH_SIZE = int(os.getenv("PUTEVKA_REGION_BATCH_SIZE", "320"))
PUTEVKA_DETAIL_PAGES_LIMIT = int(os.getenv("PUTEVKA_DETAIL_PAGES_LIMIT", "120000"))
PUTEVKA_DETAIL_BATCH_SIZE = int(os.getenv("PUTEVKA_DETAIL_BATCH_SIZE", "180"))
PUTEVKA_FETCH_WORKERS = int(os.getenv("PUTEVKA_FETCH_WORKERS", "40"))
PUTEVKA_FETCH_TIMEOUT_SECONDS = int(os.getenv("PUTEVKA_FETCH_TIMEOUT_SECONDS", "12"))
PUTEVKA_PAGE_CACHE_TTL_SECONDS = int(os.getenv("PUTEVKA_PAGE_CACHE_TTL_SECONDS", "1800"))
PUTEVKA_SITEMAP_CACHE_TTL_SECONDS = int(os.getenv("PUTEVKA_SITEMAP_CACHE_TTL_SECONDS", "3600"))
PUTEVKA_DISPLAY_PRICE_CAP = int(os.getenv("PUTEVKA_DISPLAY_PRICE_CAP", "100000"))
PUTEVKA_REGION_URLS = [
    url.strip()
    for url in os.getenv(
        "PUTEVKA_REGION_URLS",
        ",".join(
            [
                "https://www.putevka.com/krasnodar/sochi",
                "https://www.putevka.com/krasnodar/adler",
                "https://www.putevka.com/krasnodar/anapa",
                "https://www.putevka.com/krasnodar/gelendzhik",
                "https://www.putevka.com/krasnodar/tuapse",
                "https://www.putevka.com/krasnodar/lazarevskoe",
                "https://www.putevka.com/krasnodar/divnomorskoe",
                "https://www.putevka.com/kavminvody/kislovodsk",
                "https://www.putevka.com/kavminvody/essentuky",
                "https://www.putevka.com/kavminvody/pyatigorsk",
                "https://www.putevka.com/kavminvody/zheleznovodsk",
                "https://www.putevka.com/kavminvody/mineralnye-vody",
                "https://www.putevka.com/altay/belokurikha",
                "https://www.putevka.com/altay/gorno-altaysk",
                "https://www.putevka.com/altay/yarovoe",
                "https://www.putevka.com/altay/teletskoye-ozero",
                "https://www.putevka.com/krym/yalta",
                "https://www.putevka.com/krym/alushta",
                "https://www.putevka.com/krym/sudak",
                "https://www.putevka.com/krym/feodosiya",
                "https://www.putevka.com/krym/evpatoria",
                "https://www.putevka.com/krym/saky",
                "https://www.putevka.com/respublika-kareliya",
                "https://www.putevka.com/moskva",
                "https://www.putevka.com/sankt-peterburg",
                "https://www.putevka.com/kaliningrad",
                "https://www.putevka.com/respublika-dagestan",
                "https://www.putevka.com/bashkortostan",
                "https://www.putevka.com/leningradskaya-oblast",
                "https://www.putevka.com/moskovskaya-oblast",
                "https://www.putevka.com/irkutskaya-oblast",
                "https://www.putevka.com/kareliya",
                "https://www.putevka.com/primorskii-krai",
            ]
        ),
    ).split(",")
    if url.strip()
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
