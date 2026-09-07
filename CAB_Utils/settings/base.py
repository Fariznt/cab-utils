"""
Django settings for CAB_Utils project.

Environment-conditioned: every setting below is read from a plain env var via
os.environ, the same way locally and in prod. Only how those env vars get
populated differs per environment: locally via .env + python-dotenv (below),
in prod via a deploy-time fetch from AWS SSM.
This file has no AWS awareness and no dev/prod branching of its own.
"""

import base64
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Loads .env if present. 
load_dotenv(BASE_DIR / ".env")

REQUIRED_ENV_VARS = [
    "SECRET_KEY",
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
    "POLL_ERROR_LIMIT",
]
missing_vars = [var for var in REQUIRED_ENV_VARS if os.environ.get(var) is None]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

SECRET_KEY = os.environ["SECRET_KEY"]
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


# Logging --- JSON lines to stdout and to one file. Everything lands in app.log;
# picking the serious records out of it is the log destination's job, not this
# file's. In prod that's a CloudWatch metric filter on {$.level = "ERROR"} feeding
# an alarm, which is the same filtering a second level-gated handler here would
# do, minus a second copy of every error line. EventLog rows reach it through
# core/signals.py.
#
# WatchedFileHandler, and nothing rotates the file: gunicorn's workers and
# poll_seats all write this one path, and a rotating handler inside each of them
# would race to rename it out from under the others. Appending concurrently is
# safe; rotating concurrently is not. If the file ever needs bounding, logrotate
# is the thing to do it, and WatchedFileHandler already reopens the file when it
# sees the inode change.
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
            "class": "logging.handlers.WatchedFileHandler",
            "filename": LOGS_DIR / "app.log",
            "formatter": "json",
        },
    },
    "root": {
        # The file handler sits on the root logger, so it catches both the
        # EventLog rows bridged by core/signals.py and every plain
        # logger.error/exception call already in the codebase, with no
        # per-call-site changes.
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}
