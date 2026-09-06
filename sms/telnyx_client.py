import logging

import requests
from django.conf import settings
from django.utils import timezone

from core.models import EventLog
from sms.models import MessageHistory

logger = logging.getLogger(__name__)

TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"


def send_sms(user, to_number: str, text: str, tags: list[str] | None = None) -> None:
    """
    Sends one text via Telnyx, then records it to the event log and the user's
    transcript. Never raises: a network error, timeout, or non-2xx from Telnyx
    is logged (same error-log pattern as everywhere else in the app) and
    swallowed. Callers - most of them mid-webhook-request - don't need their
    own try/except, and Telnyx always gets its 200 back regardless of whether
    the outbound text actually went out. A timed-out send is genuinely
    ambiguous (Telnyx may or may not have received it), so retrying here would
    risk double-texting someone; that's worse than the rare dropped message.

    `user` may be None for a raw resend with no user record to log against
    (the message.finalized retry in webhook.py) - the original attempt already
    logged this message once, so a retry logging it again would double it.

    `tags` are echoed back on the message.finalized webhook, which is how a
    retried send is told apart from an original attempt.
    """
    payload = {"from": settings.TELNYX_PHONE_NUMBER, "to": to_number, "text": text}
    if tags:
        payload["tags"] = tags
    try:
        response = requests.post(
            TELNYX_MESSAGES_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.TELNYX_API_KEY}"},
            timeout=(5, 15),
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(f"Failed to send SMS to {to_number}")
        EventLog.objects.create(
            event_type="error", level="ERROR", user=user, message=f"Failed to send SMS: {text!r}"
        )
        return

    if user is None:
        return

    EventLog.objects.create(event_type="sms_sent", user=user, message=text)

    # Telnyx stamps inbound messages for us; outbound ones we stamp ourselves.
    history, _ = MessageHistory.objects.get_or_create(user=user)
    history.messages.append(
        {"direction": "outbound", "body": text, "at": timezone.now().isoformat()}
    )
    history.save()
