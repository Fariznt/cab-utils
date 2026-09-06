"""
Send a text via Telnyx to TELNYX_TEST_RECIPIENT, from TELNYX_PHONE_NUMBER.
Confirms outbound SMS sending works end to end.

Usage:
    python -m sms.scripts.send_ping
"""
import requests

from sms.scripts._bootstrap import require_env

TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"


def main():
    api_key = require_env("TELNYX_API_KEY")
    from_number = require_env("TELNYX_PHONE_NUMBER")
    to_number = require_env("TELNYX_TEST_RECIPIENT")

    response = requests.post(
        TELNYX_MESSAGES_URL,
        json={"from": from_number, "to": to_number, "text": "Ping! This is a test message sent by a developer to a developer phone number."},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=(5, 15),
    )
    try:
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"FAILED: {e}\n{response.text}")
        return

    message = response.json()["data"]
    print(f"Sent: id={message['id']} status={message['to'][0]['status']}")


if __name__ == "__main__":
    main()
