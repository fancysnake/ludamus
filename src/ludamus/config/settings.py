"""Django settings for ludamus project.

Generated by 'django-admin startproject' using Django 5.2.2.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/

Environment Variables:
    Required:
        - ENV: Environment name ('local' or 'production')
        - SECRET_KEY: Django secret key
        - ROOT_DOMAIN: Root domain for multi-site support
        - AUTH0_CLIENT_ID: Auth0 client ID
        - AUTH0_CLIENT_SECRET: Auth0 client secret
        - AUTH0_DOMAIN: Auth0 domain

    Production Only (when ENV=production):
        - ALLOWED_HOSTS: Comma-separated list of allowed hosts
        - DB_NAME: PostgreSQL database name
        - DB_USER: PostgreSQL username
        - DB_PASSWORD: PostgreSQL password
        - DB_HOST: PostgreSQL host (default: localhost)
        - DB_PORT: PostgreSQL port (default: 5432)

    Optional:
        - SESSION_COOKIE_DOMAIN: Session cookie domain
        - SUPPORT_EMAIL: Support email address
        - STATIC_ROOT: Static files root directory
        - MEDIA_ROOT: Media files root directory
"""

import os
from pathlib import Path
from typing import Any

import environ

env = environ.Env(DEBUG=(bool, False), USE_POSTGRES=(bool, False))


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment configuration
ENV = os.getenv("ENV", "local")
IS_PRODUCTION = ENV == "production"

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

SECRET_KEY = os.environ["SECRET_KEY"]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

# Parse comma-separated allowed hosts for production
ALLOWED_HOSTS: list[str] = []
if allowed_hosts := os.getenv("ALLOWED_HOSTS", ""):
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts.split(",")]
elif DEBUG:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", "")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.flatpages",
    # Third Party
    "django_bootstrap5",
    "django_bootstrap_icons",
    # First Party
    "ludamus.adapters.web.django.apps.WebMainConfig",
    "ludamus.adapters.db.django.apps.DBMainConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "ludamus.adapters.web.django.middlewares.SphereMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "ludamus.adapters.web.django.middlewares.RedirectErrorMiddleware",
    "django.contrib.flatpages.middleware.FlatpageFallbackMiddleware",
]

if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")

ROOT_URLCONF = "ludamus.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "ludamus.adapters.web.django.context_processors.sites",
                "ludamus.adapters.web.django.context_processors.support",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "debug": DEBUG,
            "string_if_invalid": "ERROR: Missing variable %s",
        },
    }
]

WSGI_APPLICATION = "ludamus.deploy.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

TESTING = os.getenv("TESTING", "")
DATABASES: dict[str, dict[str, Any]] = (  # type: ignore [explicit-any]
    {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    if TESTING
    else {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "dev.sqlite3"),
        }
    }
)


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        )
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "pl"

LANGUAGES = [("pl", "Polski"), ("en", "English")]

TIME_ZONE = "Europe/Warsaw"

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [BASE_DIR / "locale"]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"

STATICFILES_DIRS = [BASE_DIR / "static"]

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth

AUTH_USER_MODEL = "db_main.User"
LOGIN_URL = "/crowd/user/login"

# Sites

ROOT_DOMAIN = os.getenv("ROOT_DOMAIN")

# Auth0

AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")

# Support

SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@example.com")

INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]

# Security Settings for Production
if IS_PRODUCTION:
    # HTTPS/SSL Settings
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    USE_X_FORWARDED_PORT = True

    # Security Headers
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

    # HSTS Settings (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Session Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"  # Changed from Strict to allow OAuth callbacks
    SESSION_COOKIE_AGE = 3600  # 1 hour
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True

    # CSRF Security
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = "Lax"  # Changed from Strict to allow OAuth callbacks

    # Additional Security Settings
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

    SECURE_REDIRECT_EXEMPT: list[str] = []

    # File Upload Security
    FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
    DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
else:
    # Development settings
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SECURE = False
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = "Lax"

# Production Database Settings
if env("USE_POSTGRES"):
    DATABASES = {
        "default": {
            "ATOMIC_REQUESTS": True,
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ["DB_USER"],
            "PASSWORD": os.environ["DB_PASSWORD"],
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"connect_timeout": 10},
        }
    }


# Static files configuration for production
if IS_PRODUCTION:
    STATIC_ROOT = os.getenv("STATIC_ROOT", str(BASE_DIR / "staticfiles"))
    STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    )

    # Media files
    MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(BASE_DIR / "media"))
    MEDIA_URL = "/media/"
else:
    # Development email backend
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Cache configuration
CACHES = (
    {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "cache_table",
        }
    }
    if IS_PRODUCTION
    else {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }
)

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {module} {message}",
            "style": "{",
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "root": {"handlers": ["console"], "level": "INFO" if IS_PRODUCTION else "DEBUG"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING" if IS_PRODUCTION else "INFO",
            "propagate": False,
        },
    },
}
