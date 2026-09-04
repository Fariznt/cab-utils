"""
Telnyx webhook authentication. The caller is Telnyx rather than a Django user,
so the signature check is the whole of this endpoint's auth.
"""

import base64
import logging
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.conf import settings
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)

# How far out of date a signed webhook may be before it's treated as a replay.
SIGNATURE_TOLERANCE_SECONDS = 300


class TelnyxSignature(BasePermission):
    """
    Verifies Telnyx's Ed25519 webhook signature. The caller is Telnyx, not a
    Django user, so this is the only authentication the webhook endpoint has
    """

    message = "Invalid Telnyx signature."

    def has_permission(self, request, view):
        signature = request.headers.get("telnyx-signature-ed25519", "")
        timestamp = request.headers.get("telnyx-timestamp", "")
        try:
            # An old-but-validly-signed payload is a replay, so the timestamp is
            # checked as well as signed. Telnyx signs "<timestamp>|<raw body>".
            if abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
                logger.warning("Rejected webhook with a stale Telnyx timestamp")
                return False
            public_key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(settings.TELNYX_PUBLIC_KEY)
            )
            public_key.verify(
                base64.b64decode(signature), f"{timestamp}|".encode() + request.body
            )
        except (InvalidSignature, ValueError, TypeError):
            logger.warning("Rejected webhook with an invalid Telnyx signature")
            return False
        return True
