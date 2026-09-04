"""
Unit tests for telnyx_client.send_sms itself - the Telnyx call and the
bookkeeping (event log, transcript) around it now live in the same function,
and every other test in this app mocks send_sms wholesale (see helpers.py) to
avoid a real Telnyx call, which also hides that bookkeeping from those tests.
This is the one place it's exercised for real.
"""

from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import EventLog, User
from sms.models import MessageHistory
from sms.telnyx_client import TELNYX_MESSAGES_URL, send_sms

USER_NUMBER = "+15551234567"
SERVICE_NUMBER = "+15559998888"


@override_settings(TELNYX_PHONE_NUMBER=SERVICE_NUMBER, TELNYX_API_KEY="test-key")
class SendSmsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_num=USER_NUMBER)
        post_patcher = patch("sms.telnyx_client.requests.post")
        self.post = post_patcher.start()
        self.addCleanup(post_patcher.stop)

    def test_calls_telnyx_with_the_right_payload(self):
        send_sms(self.user, USER_NUMBER, "hello there")

        self.post.assert_called_once_with(
            TELNYX_MESSAGES_URL,
            json={"from": SERVICE_NUMBER, "to": USER_NUMBER, "text": "hello there"},
            headers={"Authorization": "Bearer test-key"},
        )

    def test_tags_are_included_when_given(self):
        send_sms(self.user, USER_NUMBER, "hello there", tags=["retry"])

        self.assertEqual(self.post.call_args.kwargs["json"]["tags"], ["retry"])

    def test_records_the_send_to_the_event_log(self):
        send_sms(self.user, USER_NUMBER, "hello there")

        self.assertTrue(
            EventLog.objects.filter(
                event_type="sms_sent", user=self.user, message="hello there"
            ).exists()
        )

    def test_records_the_send_to_the_transcript(self):
        send_sms(self.user, USER_NUMBER, "hello there")

        messages = MessageHistory.objects.get(user=self.user).messages
        self.assertEqual(
            [(m["direction"], m["body"]) for m in messages], [("outbound", "hello there")]
        )

    def test_a_failed_send_is_not_logged(self):
        self.post.return_value.raise_for_status.side_effect = RuntimeError("telnyx down")

        with self.assertRaises(RuntimeError):
            send_sms(self.user, USER_NUMBER, "hello there")

        self.assertFalse(EventLog.objects.filter(event_type="sms_sent").exists())
        self.assertFalse(MessageHistory.objects.exists())

    def test_no_bookkeeping_without_a_user(self):
        # the message.finalized retry path (webhook.py) resends with no user in
        # scope - the original attempt already logged this message once, so a
        # retry logging it again would double it
        send_sms(None, USER_NUMBER, "hello there")

        self.assertFalse(EventLog.objects.filter(event_type="sms_sent").exists())
        self.assertFalse(MessageHistory.objects.exists())
