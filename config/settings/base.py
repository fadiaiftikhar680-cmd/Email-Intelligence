"""
Base settings for Email Intelligence Platform.
Fulfills Part 1.4, Part 3.6, Part 4, and Part 8.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-email-intelligence-platform-secret-key-change-in-prod")
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

    # Third-party
    "rest_framework",
    "corsheaders",
    "drf_spectacular",

    # Core system apps
    "apps.accounts",
    "apps.audit",
    "apps.dashboard",
    "apps.email_verifier",
    "apps.bulk_processing",
    "apps.email_finder",
    "apps.intelligence",
    "apps.history_reports",
    "apps.api_management",
    "apps.admin_management",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.AutoLoginMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database Configuration: PostgreSQL when DB_ENGINE is postgres or DATABASE_URL is provided, else SQLite
DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").lower()
if DB_ENGINE in ("postgres", "postgresql") or os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "email_intelligence"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    if os.environ.get("VERCEL"):
        import shutil
        tmp_db = Path("/tmp/db.sqlite3")
        orig_db = BASE_DIR / "db.sqlite3"
        if not tmp_db.exists() and orig_db.exists():
            try:
                shutil.copy2(orig_db, tmp_db)
            except Exception:
                pass
        db_file = tmp_db
    else:
        db_file = BASE_DIR / "db.sqlite3"

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": db_file,
            "OPTIONS": {
                "timeout": 30,
            },
        }
    }

# Custom User Model (Part 4)
AUTH_USER_MODEL = "accounts.User"

# Password Hashers (Argon2 per Part 3.6 & Part 8.1)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework & OpenAPI Docs
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Email Intelligence Platform Public API",
    "DESCRIPTION": "Find. Verify. Enrich. Public API for email discovery and deliverability verification.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Celery & Background Jobs
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "True").lower() == "true"
CELERY_TASK_EAGER_PROPAGATES = True

# Outbound Probing Configuration
SMTP_PROBING_ENABLED = os.environ.get("SMTP_PROBING_ENABLED", "True").lower() == "true"
SMTP_PROBE_HELO = os.environ.get("SMTP_PROBE_HELO", "mail.emailintelligence.local")
SMTP_PROBE_MAIL_FROM = os.environ.get("SMTP_PROBE_MAIL_FROM", "verify@emailintelligence.local")

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# External AI & Integration API Keys (Loaded from .env)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
SERP_API_KEY = os.environ.get("SERP_API_KEY", "")
CUSTOM_API_KEY = os.environ.get("CUSTOM_API_KEY", "")
API_KEY = os.environ.get("API_KEY", "")

