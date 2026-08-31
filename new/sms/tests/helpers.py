"""
Shared setup for the sms tests.

Tests drive the app the way Telnyx does - a signed POST of a real-shaped webhook
payload - rather than calling the handlers directly, so the signature check, the
event routing and the conversation flow are all exercised as one piece. Telnyx
itself is never called: every outbound send is captured by a mock.
"""

import base64
import json
import time
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import CourseSession, User
from sms.models import ConversationState
from seat_signal.utils import get_current_sem_id

# A throwaway keypair stands in for Telnyx's, so tests sign their own payloads
# and the real signature check runs on every request instead of being mocked out.
_PRIVATE_KEY = Ed25519PrivateKey.generate()
TEST_PUBLIC_KEY = base64.b64encode(_PRIVATE_KEY.public_key().public_bytes_raw()).decode()

USER_NUMBER = "+15551234567"
SERVICE_NUMBER = "+15559998888"

# Fixture courses are created in whatever semester the flow currently scopes to,
# so the suite doesn't need updating every time REGISTRATION_PERIODS does.
CURRENT_SEM_ID = get_current_sem_id()
FIXTURE_COURSES = [
    ("CSCI 0320", "Introduction to Software Engineering"),
    ("CSCI 0330", "Introduction to Computer Systems"),
    ("MATH 0100", "Introductory Calculus, Part II"),
]


def sign(body: bytes, timestamp: str | None = None, key=_PRIVATE_KEY) -> dict:
    """Builds the webhook signature headers Telnyx sends alongside a raw body."""
    timestamp = timestamp or str(int(time.time()))
    signature = base64.b64encode(key.sign(f"{timestamp}|".encode() + body))
    return {
        "telnyx-signature-ed25519": signature.decode(),
        "telnyx-timestamp": timestamp,
    }


@override_settings(TELNYX_PUBLIC_KEY=TEST_PUBLIC_KEY)
class SmsTestCase(TestCase):
    def setUp(self):
        # Telnyx is never actually called; every send is captured here instead.
        # send_sms is called from two modules - inbound_state_handler for
        # conversation replies, webhook for the message.finalized retry - so
        # both names point at one mock, keeping every send in a single ordered
        # list.
        send_patcher = patch("sms.views.inbound_state_handler.send_sms")
        self.send_sms = send_patcher.start()
        self.addCleanup(send_patcher.stop)
        retry_patcher = patch("sms.views.webhook.send_sms", self.send_sms)
        retry_patcher.start()
        self.addCleanup(retry_patcher.stop)

        # The deliberate pauses (between the two help messages, before a retry)
        # are real-world pacing with no place in a test run.
        sleep_patcher = patch("sms.views.webhook.time.sleep")
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        self.url = reverse("sms:telnyx-webhook")
        self.sessions = {
            code: CourseSession.objects.create(
                crn=f"1000{i}", code=code, section="S01",
                sem_id=CURRENT_SEM_ID, title=title,
            )
            for i, (code, title) in enumerate(FIXTURE_COURSES)
        }

    # Request builders

    def post_webhook(self, payload, headers=None):
        body = json.dumps(payload).encode()
        return self.client.post(
            self.url,
            data=body,
            content_type="application/json",
            headers=sign(body) if headers is None else headers,
        )

    def text(self, body, from_number=USER_NUMBER, **kwargs):
        """One inbound SMS, shaped the way Telnyx delivers it."""
        return self.post_webhook({
            "data": {
                "event_type": "message.received",
                "payload": {
                    "id": "msg-inbound",
                    "from": {"phone_number": from_number},
                    "to": [{"phone_number": SERVICE_NUMBER}],
                    "text": body,
                    "received_at": "2026-08-28T12:00:00.000Z",
                },
            }
        }, **kwargs)

    def finalized(self, errors=None, tags=None, text="a sent message", to=USER_NUMBER):
        """One delivery receipt for a message we sent."""
        return self.post_webhook({
            "data": {
                "event_type": "message.finalized",
                "payload": {
                    "id": "msg-outbound",
                    "from": {"phone_number": SERVICE_NUMBER},
                    "to": [{"phone_number": to}],
                    "text": text,
                    "tags": tags or [],
                    "errors": errors or [],
                },
            }
        })

    # Outbound assertions

    def sent(self):
        """The body of every text sent since the last reset, in order."""
        return [call.args[2] for call in self.send_sms.call_args_list]

    def last_sent(self):
        return self.sent()[-1]

    def assert_sent(self, *expected):
        self.assertEqual(self.sent(), list(expected))

    def assert_sent_nothing(self):
        self.assertEqual(self.sent(), [])

    # State accessors

    def user(self, number=USER_NUMBER):
        return User.objects.get(phone_num=number)

    def conversation_state(self, number=USER_NUMBER):
        return ConversationState.objects.get(user=self.user(number))

    def onboard(self, number=USER_NUMBER):
        """Gets a number past first contact, so tests start at the course step."""
        self.text("hello", from_number=number)
        self.send_sms.reset_mock()
        return self.user(number)

    def set_state(self, state, code="", section="", sem_id=CURRENT_SEM_ID, number=USER_NUMBER):
        """Drops an onboarded user straight into a mid-flow state."""
        conversation_state = self.conversation_state(number)
        conversation_state.state = state
        conversation_state.pending_code = code
        conversation_state.pending_section = section
        conversation_state.pending_sem_id = sem_id if code else ""
        conversation_state.save()
        return conversation_state
