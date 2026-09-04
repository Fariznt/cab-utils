"""
Django settings for CAB_Utils project.

Environment-conditioned: every setting below is read from a plain env var via
os.environ, the same way locally and in prod. Only how those env vars get
populated differs per environment: locally via .env + python-dotenv (below),
in prod via a deploy-time fetch from AWS SSM.
This file has no AWS awareness and no dev/prod branching of its own.
"""

import base64
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Loads .env if present. 
load_dotenv(BASE_DIR / ".env")

REQUIRED_ENV_VARS = [
    "SECRET_KEY",
    "DEBUG",
    "ALLOWED_HOSTS",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "PHONE_ENCRYPTION_KEY",
    "SIGNAL_CAP",
    "TELNYX_API_KEY",
    "TELNYX_PUBLIC_KEY",
    "TELNYX_PHONE_NUMBER",
    "PRIVACY_URL",
    "REVIEW_THRESHOLD",
    "POLL_ERROR_LIMIT",
]
missing_vars = [var for var in REQUIRED_ENV_VARS if os.environ.get(var) is None]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

SECRET_KEY = os.environ["SECRET_KEY"]
DEBUG = os.environ["DEBUG"].lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [h.strip() for h in os.environ["ALLOWED_HOSTS"].split(",") if h.strip()]

# AES-256-SIV key for core.fields.EncryptedPhoneField, base64-encoded 64 bytes.
PHONE_ENCRYPTION_KEY = os.environ["PHONE_ENCRYPTION_KEY"]
if len(base64.b64decode(PHONE_ENCRYPTION_KEY)) != 64:
    raise ValueError("PHONE_ENCRYPTION_KEY must decode to exactly 64 bytes (AES-256-SIV)")

# Max active SeatSignal watches per user (see seat_signal.services.create_watch),
# a guardrail against SMS-cost/abuse, not just a UX nicety.
SIGNAL_CAP = int(os.environ["SIGNAL_CAP"])

# Telnyx - read by sms/telnyx_client.py (outbound) and sms/views/auth.py (inbound
# webhook). Same vars sms/scripts/ use for their standalone connectivity checks.
TELNYX_API_KEY = os.environ["TELNYX_API_KEY"]
# Ed25519 public key from the Telnyx portal, used to verify inbound webhook
# signatures (see sms.views.auth.TelnyxSignature).
TELNYX_PUBLIC_KEY = os.environ["TELNYX_PUBLIC_KEY"]
TELNYX_PHONE_NUMBER = os.environ["TELNYX_PHONE_NUMBER"]

# Terms & Privacy link sent in the SMS opt-in message (sms/conversation.py).
PRIVACY_URL = os.environ["PRIVACY_URL"]

# Log level at/above which a record also lands in logs/review.log, the file
# CloudWatch watches for alerting. Same vocabulary as core.models.EventLog.LEVELS.
REVIEW_THRESHOLD = logging.getLevelNamesMapping().get(os.environ["REVIEW_THRESHOLD"])
if REVIEW_THRESHOLD is None:
    raise ValueError("REVIEW_THRESHOLD must be a logging level name (e.g. ERROR)")

# Consecutive C@B check failures before poll_seats gives up and exits for systemd
# to restart
POLL_ERROR_LIMIT = int(os.environ["POLL_ERROR_LIMIT"])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "core",
    "seat_signal",
    "sms",
    "ops",
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

ROOT_URLCONF = "CAB_Utils.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "CAB_Utils.wsgi.application"


# Database

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": os.environ["POSTGRES_PORT"],
    }
}


# Auth

AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Logging --- JSON lines to two rotating files: app.log gets everything (so
# update_db/poll_seats' logger.info calls and the poll loop's heartbeat land
# somewhere durable), review.log gets only REVIEW_THRESHOLD and above. The split
# is what makes alerting cheap downstream: CloudWatch alarms on review.log's line
# count, with no log parsing, since the filtering already happened here.
# EventLog rows reach both through core/signals.py.
#
# Both files rotate: at maxBytes the handler renames app.log -> app.log.1 (older
# backups shifting down, the oldest past backupCount deleted) and starts fresh,
# capping disk use at roughly maxBytes * (backupCount + 1) per file.
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "CAB_Utils.log_formatter.JsonFormatter"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "app.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "json",
        },
        "review_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "review.log",
            "level": REVIEW_THRESHOLD,
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "json",
        },
    },
    "root": {
        # review_file sits on the root logger, so it catches both the EventLog
        # rows bridged by core/signals.py and every plain logger.error/exception
        # call already in the codebase, with no per-call-site changes.
        "handlers": ["console", "file", "review_file"],
        "level": "INFO",
    },
}
