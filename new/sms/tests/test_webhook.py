"""
The webhook as transport: who's allowed to POST it, which events it acts on,
what it records, and how it reacts to a failed send. The conversation itself is
covered in test_picking_flow.py.
"""

import json
import time
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.models import EventLog, User
from sms.models import ConversationState, MessageHistory
from sms.tests.helpers import USER_NUMBER, SmsTestCase, sign
from sms.views import (
    GENERIC_ERROR_MESSAGE,
    HELP_MESSAGE,
    OPT_IN_MESSAGE,
    RETRY_TAG,
    SIGNATURE_TOLERANCE_SECONDS,
)


class SignatureTests(SmsTestCase):
    """
    The signature is this endpoint's only authentication - a request that fails
    it could otherwise claim to be any phone number and drive that user's
    conversation, so every rejection path is pinned down here.
    """

    def test_valid_signature_is_accepted(self):
        self.assertEqual(self.text("hello").status_code, 200)

    def test_unsigned_request_is_rejected(self):
        response = self.text("hello", headers={})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_signature_from_the_wrong_key_is_rejected(self):
        body = json.dumps({"data": {"event_type": "message.received"}}).encode()
        headers = sign(body, key=Ed25519PrivateKey.generate())

        response = self.text("hello", headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_tampered_body_is_rejected(self):
        # signature covers a different body than the one actually posted
        headers = sign(b'{"data": {}}')

        response = self.text("hello", headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_stale_signature_is_rejected(self):
        # correctly signed, but old enough to be a captured-and-replayed request
        stale = str(int(time.time()) - SIGNATURE_TOLERANCE_SECONDS - 60)
        body = json.dumps({"data": {"event_type": "message.received"}}).encode()

        response = self.text("hello", headers=sign(body, timestamp=stale))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_garbage_timestamp_is_rejected(self):
        body = json.dumps({"data": {}}).encode()
        headers = sign(body)
        headers["telnyx-timestamp"] = "not-a-timestamp"

        self.assertEqual(self.text("hello", headers=headers).status_code, 403)


class EventRoutingTests(SmsTestCase):
    def test_unhandled_event_type_is_ignored(self):
        response = self.post_webhook({
            "data": {"event_type": "message.sent", "payload": {"id": "msg-1"}}
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())
        self.assert_sent_nothing()

    def test_empty_body_does_not_crash(self):
        self.assertEqual(self.post_webhook({}).status_code, 200)

    def test_message_without_text_is_silently_ignored(self):
        # e.g. an MMS with no text body - nothing to act on, so no reply at all
        self.onboard()

        response = self.text(None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.conversation_state().state, ConversationState.AWAITING_COURSE
        )
        self.assert_sent_nothing()


class NewUserOnboardingTests(SmsTestCase):
    def test_first_message_creates_an_opted_in_user_at_the_course_step(self):
        self.text("hello")

        user = self.user()
        self.assertTrue(user.opt_in_status.is_opted_in)
        self.assertEqual(user.conversation_state.state, ConversationState.AWAITING_COURSE)

    def test_first_message_gets_the_opt_in_greeting_and_nothing_else(self):
        self.text("hello")

        self.assert_sent(OPT_IN_MESSAGE)

    def test_first_message_is_not_consumed_as_a_course(self):
        # first contact is a greeting, so the course question starts fresh after it
        self.text("CSCI 0320")

        conversation_state = self.conversation_state()
        self.assertEqual(conversation_state.pending_code, "")
        self.assertEqual(conversation_state.state, ConversationState.AWAITING_COURSE)

    def test_known_number_is_not_recreated_or_regreeted(self):
        self.onboard()

        self.text("hi again")

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(EventLog.objects.filter(event_type="account_created").count(), 1)
        self.assertNotIn(OPT_IN_MESSAGE, self.sent())

    def test_help_as_a_first_message_is_answered_before_the_greeting(self):
        self.text("HELP")

        self.assert_sent(HELP_MESSAGE, OPT_IN_MESSAGE)


class RecordKeepingTests(SmsTestCase):
    """
    Everything ops can see downstream comes from these two records, so they're
    asserted on their own rather than as a side note of the flow tests. Only
    the inbound half is checked here - send_sms is mocked wholesale in every
    test in this suite (see SmsTestCase), so the outbound sms_sent/transcript
    writes it makes are unobservable at this level. Those are covered directly
    in test_telnyx_client.py, against the real send_sms.
    """

    def test_account_creation_is_logged(self):
        self.text("hello")

        self.assertTrue(
            EventLog.objects.filter(event_type="account_created", user=self.user()).exists()
        )

    def test_inbound_message_is_logged(self):
        self.text("hello")

        self.assertEqual(
            EventLog.objects.filter(event_type="sms_received").values_list("message", flat=True)[0],
            "hello",
        )

    def test_transcript_records_the_inbound_message(self):
        self.text("hello")

        messages = MessageHistory.objects.get(user=self.user()).messages
        self.assertEqual([(m["direction"], m["body"]) for m in messages], [("inbound", "hello")])
        # inbound carries Telnyx's timestamp, stamped by us for outbound (see test_telnyx_client.py)
        self.assertEqual(messages[0]["at"], "2026-08-28T12:00:00.000Z")


class FinalizedEventTests(SmsTestCase):
    """
    A send that Telnyx couldn't deliver comes back as message.finalized with an
    errors array. Retrying is worth it for a transient failure and never worth
    it otherwise - a retry loop would burn money and get the number flagged.
    """

    def test_successful_delivery_does_nothing(self):
        self.finalized()

        self.assertFalse(EventLog.objects.filter(event_type="error").exists())
        self.assert_sent_nothing()

    def test_transient_failure_is_logged_and_retried_once(self):
        self.finalized(errors=[{"code": "40300", "title": "Temporary failure"}])

        error = EventLog.objects.get(event_type="error")
        self.assertIn("40300", error.message)
        self.assertEqual(error.metadata["message_id"], "msg-outbound")

        self.send_sms.assert_called_once_with(
            None, USER_NUMBER, "a sent message", tags=[RETRY_TAG]
        )

    def test_permanent_failure_is_not_retried(self):
        for code in ["40001", "47000"]:
            with self.subTest(code=code):
                self.send_sms.reset_mock()

                self.finalized(errors=[{"code": code, "title": "Permanent failure"}])

                self.assert_sent_nothing()

    def test_a_failed_retry_is_not_retried_again(self):
        # the retry tag is how a second attempt is told apart from a first one
        self.finalized(errors=[{"code": "40300"}], tags=[RETRY_TAG])

        self.assertTrue(EventLog.objects.filter(event_type="error").exists())
        self.assert_sent_nothing()


class StateMessageErrorHandlingTests(SmsTestCase):
    """
    _handle_state_message runs inside its own savepoint (see views.py) so that a
    failure partway through - a partial write, a stale row - rolls back cleanly
    instead of leaving the transaction unable to run the recovery writes below
    it (the EventLog entry and the reply to the user). A crash while awaiting a
    course/section/confirmation/removal reply is simulated for each state to
    prove the recovery path itself doesn't depend on which state it happened in.
    """

    def test_unhandled_exception_gets_a_generic_reply_and_is_logged(self):
        self.onboard()

        with patch("sms.views.inbound_state_handler._register_course", side_effect=RuntimeError("boom")):
            response = self.text("CSCI 0320")

        self.assertEqual(response.status_code, 200)
        self.assert_sent(GENERIC_ERROR_MESSAGE)
        error = EventLog.objects.get(event_type="error")
        self.assertIn("CSCI 0320", error.message)

    def test_failed_write_inside_the_handler_does_not_block_the_recovery_writes(self):
        # The handler writes the matched course, then texts the section prompt.
        # Failing that send after the write is the case the savepoint exists for:
        # the write has to roll back while the recovery writes below still land.
        self.onboard()
        self.send_sms.side_effect = [RuntimeError("telnyx down"), None]

        response = self.text("CSCI 0320")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.last_sent(), GENERIC_ERROR_MESSAGE)
        self.assertTrue(EventLog.objects.filter(event_type="error").exists())
        # the failed write must not have landed
        conversation_state = self.conversation_state()
        self.assertEqual(conversation_state.pending_code, "")
        self.assertEqual(conversation_state.state, ConversationState.AWAITING_COURSE)

    def test_error_in_any_state_is_recovered_the_same_way(self):
        targets = {
            ConversationState.AWAITING_COURSE: "sms.views.inbound_state_handler._register_course",
            ConversationState.AWAITING_SECTION: "sms.views.inbound_state_handler._register_section",
        }
        self.onboard()
        for state, target in targets.items():
            with self.subTest(state=state):
                self.send_sms.reset_mock()
                EventLog.objects.all().delete()
                self.set_state(state, code="CSCI 0320")

                with patch(target, side_effect=RuntimeError("boom")):
                    response = self.text("S01")

                self.assertEqual(response.status_code, 200)
                self.assert_sent(GENERIC_ERROR_MESSAGE)
                self.assertTrue(EventLog.objects.filter(event_type="error").exists())
