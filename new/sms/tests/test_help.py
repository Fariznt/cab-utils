"""
HELP. The generic HELP_MESSAGE now goes out from post() itself, ahead of the
opt-in/opt-out gate, so carriers get an answer to HELP no matter what state the
user is in - opted out included. The state-specific follow-up still comes from
_handle_state_message, one beat later, only for an opted-in known user.
"""

from sms.models import ConversationState
from seat_signal.utils import get_sem_str
from sms.tests.helpers import CURRENT_SEM_ID, SmsTestCase
from sms.views import (
    HELP_CONFIRMATION_TEMPLATE,
    HELP_COURSE_MESSAGE,
    HELP_MESSAGE,
    HELP_REMOVAL_MESSAGE,
    HELP_SECTION_MESSAGE,
    OPT_IN_MESSAGE,
)

# The confirmation step's help names the selection it is asking about, so it
# depends on what the test put in the conversation state below.
CONFIRMATION_HELP = HELP_CONFIRMATION_TEMPLATE.format(
    selection=f"CSCI 0320 S01 ({get_sem_str(CURRENT_SEM_ID)})"
)

STATE_HELP_MESSAGES = {
    ConversationState.AWAITING_COURSE: HELP_COURSE_MESSAGE,
    ConversationState.AWAITING_SECTION: HELP_SECTION_MESSAGE,
    ConversationState.AWAITING_CONFIRMATION: CONFIRMATION_HELP,
    ConversationState.AWAITING_REMOVAL: HELP_REMOVAL_MESSAGE,
}


class HelpTests(SmsTestCase):
    def test_help_sends_generic_then_tailored_message_per_state(self):
        self.onboard()
        for state, tailored_message in STATE_HELP_MESSAGES.items():
            with self.subTest(state=state):
                self.set_state(state, code="CSCI 0320", section="S01")
                self.send_sms.reset_mock()

                self.text("HELP")

                self.assert_sent(HELP_MESSAGE, tailored_message)

    def test_help_never_changes_state_or_pending_selections(self):
        self.onboard()
        for state in STATE_HELP_MESSAGES:
            with self.subTest(state=state):
                self.set_state(state, code="CSCI 0320", section="S01")

                self.text("HELP")

                conversation_state = self.conversation_state()
                self.assertEqual(conversation_state.state, state)
                self.assertEqual(conversation_state.pending_code, "CSCI 0320")

    def test_help_is_case_and_whitespace_insensitive(self):
        self.onboard()

        self.text("  help ")

        self.assert_sent(HELP_MESSAGE, STATE_HELP_MESSAGES[ConversationState.AWAITING_COURSE])

    def test_help_as_a_first_message_only_gets_the_greeting(self):
        # a brand-new number has no conversation state to tailor help to yet -
        # covered fully in test_webhook.py, asserted again here as the one place
        # every HELP variant is gathered
        self.text("HELP")

        self.assert_sent(HELP_MESSAGE, OPT_IN_MESSAGE)

    def test_help_while_opted_out_still_gets_the_generic_message(self):
        self.onboard()
        self.text("STOP")
        self.send_sms.reset_mock()

        self.text("HELP")

        self.assert_sent(HELP_MESSAGE)
