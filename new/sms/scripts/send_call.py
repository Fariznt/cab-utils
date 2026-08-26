"""
Place an outbound call via Telnyx Call Control to TELNYX_TEST_RECIPIENT, from
TELNYX_PHONE_NUMBER. One-off test to see whether calling works with no portal
setup beyond an API key (Telnyx Call Control requires a connection_id tied to
a Call Control Application, unlike SMS - see send_ping.py for the analogous
messaging test, which needs no connection_id).

Usage:
    python -m sms.scripts.send_call
"""
import requests

from sms.scripts._bootstrap import require_env

TELNYX_CALLS_URL = "https://api.telnyx.com/v2/calls"


def main():
    api_key = require_env("TELNYX_API_KEY")
    from_number = require_env("TELNYX_PHONE_NUMBER")
    to_number = require_env("TELNYX_TEST_RECIPIENT")

    response = requests.post(
        TELNYX_CALLS_URL,
        json={"connection_id": "placeholder", "from": from_number, "to": to_number},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"FAILED: {e}\n{response.text}")
        return

    call = response.json()["data"]
    print(f"Call initiated: call_control_id={call['call_control_id']}")


if __name__ == "__main__":
    main()
