import requests
from django.conf import settings

TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"


def send_sms(to: str, text: str, tags: list[str] | None = None) -> None:
    """
    Sends one text via Telnyx. Raises on failure - callers decide how to handle it.

    `tags` are echoed back on the message.finalized webhook, which is how a
    retried send is told apart from an original attempt.
    """
    payload = {"from": settings.TELNYX_PHONE_NUMBER, "to": to, "text": text}
    if tags:
        payload["tags"] = tags
    response = requests.post(
        TELNYX_MESSAGES_URL,
        json=payload,
        headers={"Authorization": f"Bearer {settings.TELNYX_API_KEY}"},
    )
    response.raise_for_status()

