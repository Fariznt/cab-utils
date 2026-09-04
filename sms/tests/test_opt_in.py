"""
STOP/START gating, which sits above the conversation state machine. These are
carrier compliance requirements, not product choices: an opted-out number has
to stay quiet, and STOP has to work from anywhere.
"""

from sms.models import ConversationState, OptInStatus
from sms.tests.helpers import SmsTestCase
from sms.views import OPT_IN_MESSAGE, OPT_OUT_MESSAGE, STOP_KEYWORDS


class OptOutTests(SmsTestCase):
    def test_stop_opts_the_user_out_and_confirms(self):
        self.onboard()

        self.text("STOP")

        self.assertFalse(self.user().opt_in_status.is_opted_in)
        self.assert_sent(OPT_OUT_MESSAGE)

    def test_every_stop_keyword_opts_the_user_out(self):
        self.onboard()

        for keyword in STOP_KEYWORDS:
            with self.subTest(keyword=keyword):
                OptInStatus.objects.update(is_opted_in=True)

                self.text(keyword)

                self.assertFalse(self.user().opt_in_status.is_opted_in)

    def test_stop_is_case_and_whitespace_insensitive(self):
        self.onboard()

        self.text("  stop ")

        self.assertFalse(self.user().opt_in_status.is_opted_in)

    def test_stop_works_from_every_conversation_state(self):
        self.onboard()
        states = [
            ConversationState.AWAITING_COURSE,
            ConversationState.AWAITING_SECTION,
            ConversationState.AWAITING_CONFIRMATION,
            ConversationState.AWAITING_REMOVAL,
        ]
        for state in states:
            with self.subTest(state=state):
                OptInStatus.objects.update(is_opted_in=True)
                self.set_state(state, code="CSCI 0320", section="S01")

                self.text("STOP")

                self.assertFalse(self.user().opt_in_status.is_opted_in)

    def test_stop_from_a_brand_new_number_opts_out_instead_of_greeting(self):
        # a cold number whose first word is STOP is opting out, not signing up
        self.text("STOP")

        self.assertFalse(self.user().opt_in_status.is_opted_in)
        self.assert_sent(OPT_OUT_MESSAGE)

    def test_opted_out_user_gets_no_reply(self):
        self.onboard()
        self.text("STOP")
        self.send_sms.reset_mock()

        self.text("CSCI 0320")

        self.assert_sent_nothing()
        self.assertEqual(self.conversation_state().pending_code, "")


class OptInTests(SmsTestCase):
    def test_start_re_opts_the_user_in_and_greets_them(self):
        self.onboard()
        self.text("STOP")
        self.send_sms.reset_mock()

        self.text("START")

        self.assertTrue(self.user().opt_in_status.is_opted_in)
        self.assert_sent(OPT_IN_MESSAGE)

    def test_start_returns_a_mid_flow_user_to_the_course_step(self):
        self.onboard()
        self.set_state(ConversationState.AWAITING_CONFIRMATION, code="CSCI 0320", section="S01")
        self.text("STOP")

        self.text("START")

        self.assertEqual(self.conversation_state().state, ConversationState.AWAITING_COURSE)
