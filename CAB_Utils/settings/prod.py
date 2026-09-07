"""Production settings. Selected by DJANGO_SETTINGS_MODULE in the process environment."""

from .base import *  # noqa: F403

DEBUG = False

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
