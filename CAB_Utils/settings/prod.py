"""Production settings. Selected by DJANGO_SETTINGS_MODULE in the process environment."""

from .base import *  # noqa: F403

DEBUG = False

# Hashed filenames + far-future cache headers, and compression (gzip/brotli)
# served straight off disk by whitenoise. Manifest-based, so it requires
# collectstatic to have run at deploy time - left out of dev.py since local
# dev never runs collectstatic.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# TLS terminates at the proxy in front of gunicorn, so requests reach Django as
# plain HTTP over loopback. This header is how Django learns the original request
# was HTTPS, which the three settings below all depend on. Trusting it is only
# safe because the proxy sets the header itself and nothing else can reach
# gunicorn directly.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Answer plain HTTP with a redirect to HTTPS instead of serving the request.
SECURE_SSL_REDIRECT = True

# Keep the admin session and CSRF cookies off any unencrypted connection.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
