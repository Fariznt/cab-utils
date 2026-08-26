import requests
from django.conf import settings

TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"


def send_sms(to: str, text: str) -> None:
    """Sends one text via Telnyx. Raises on failure - callers decide how to handle it."""
    response = requests.post(
        TELNYX_MESSAGES_URL,
        json={"from": settings.TELNYX_PHONE_NUMBER, "to": to, "text": text},
        headers={"Authorization": f"Bearer {settings.TELNYX_API_KEY}"},
    )
    response.raise_for_status()

