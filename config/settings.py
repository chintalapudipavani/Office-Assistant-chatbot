"""
Django settings for the AI-Powered Intelligent Office Assistant.

All secrets and tunable values are read from environment variables (the .env file).
Nothing secret is stored in this file.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Read the .env file in the project root (if it exists) into environment variables.
load_dotenv(BASE_DIR / ".env")

# Windows workaround: PyTorch and FAISS can each load their own OpenMP library, which
# sometimes crashes with "OMP: Error #15". This setting allows both to coexist.
# It is a known workaround, not a perfect fix. Must be set before torch/faiss import.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
# Silences a harmless warning from the tokenizers library.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


# ---------------------------------------------------------------------------
# Helpers to read environment variables safely
# ---------------------------------------------------------------------------
def env_str(name, default=""):
    return os.getenv(name, default).strip()


def env_bool(name, default):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    raw = os.getenv(name, "").strip()
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be a whole number, but it is {raw!r}. "
            f"Fix it in your .env file."
        )


def env_float(name, default):
    raw = os.getenv(name, "").strip()
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be a number, but it is {raw!r}. "
            f"Fix it in your .env file."
        )


def env_list(name, default):
    raw = os.getenv(name, "").strip() or default
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core Django settings
# ---------------------------------------------------------------------------
# This obviously-fake key is used ONLY for local development when .env has no key.
# It is refused when DEBUG is False.
_INSECURE_DEV_KEY = "insecure-local-development-key-do-not-use-in-production"
SECRET_KEY = env_str("DJANGO_SECRET_KEY") or _INSECURE_DEV_KEY

DEBUG = env_bool("DJANGO_DEBUG", True)

if not DEBUG and SECRET_KEY == _INSECURE_DEV_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set in .env when DJANGO_DEBUG is False."
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1","localhost","office-assistant-chatbot.onrender.com")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Our apps
    "accounts",
    "documents",
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # CSRF protection for every POST form
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database (SQLite for development)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"            # where anonymous users are sent when a page needs login
LOGIN_REDIRECT_URL = "chat"    # where users go after logging in
LOGOUT_REDIRECT_URL = "home"   # where users go after logging out

# Only send cookies over HTTPS when you deploy with HTTPS. Keep False for local http.
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env_str("DJANGO_TIME_ZONE", "UTC") or "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static and media files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Uploaded PDFs are saved here. They are deliberately NOT served by a public URL,
# because they may be confidential. Only our own code reads them.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Upload and chat limits
# ---------------------------------------------------------------------------
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 10)
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
MAX_QUESTION_CHARS = env_int("MAX_QUESTION_CHARS", 1000)
CHAT_HISTORY_MESSAGES = env_int("CHAT_HISTORY_MESSAGES", 6)

# ---------------------------------------------------------------------------
# RAG settings
# ---------------------------------------------------------------------------
RAG_DIR = BASE_DIR / "data" / "vector_store"
RAG_INDEX_PATH = RAG_DIR / "faiss.index"

EMBEDDING_MODEL_NAME = env_str(
    "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
)
CHUNK_SIZE = env_int("CHUNK_SIZE", 800)
CHUNK_OVERLAP = env_int("CHUNK_OVERLAP", 150)
RETRIEVAL_TOP_K = env_int("RETRIEVAL_TOP_K", 5)
RETRIEVAL_MIN_SCORE = env_float("RETRIEVAL_MIN_SCORE", 0.30)

if CHUNK_OVERLAP >= CHUNK_SIZE:
    raise ImproperlyConfigured("CHUNK_OVERLAP must be smaller than CHUNK_SIZE in .env.")

# ---------------------------------------------------------------------------
# LLM settings (any OpenAI-compatible API)
# ---------------------------------------------------------------------------
LLM_API_KEY = env_str("LLM_API_KEY")
LLM_BASE_URL = env_str("LLM_BASE_URL")  # empty = the official OpenAI endpoint
LLM_MODEL = env_str("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SECONDS = env_int("LLM_TIMEOUT_SECONDS", 60)
LLM_TEMPERATURE = env_float("LLM_TEMPERATURE", 0.1)
LLM_MAX_TOKENS = env_int("LLM_MAX_TOKENS", 600)

# ---------------------------------------------------------------------------
# Logging (messages appear in the Command Prompt running the server)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "loggers": {
        "rag": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "documents": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "chat": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
