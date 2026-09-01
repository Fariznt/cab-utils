"""
The course-picking conversation: course -> section -> confirm -> watch created.
Replies here are exactly formatted (matching a fixture CourseSession verbatim)
so these tests stay about the flow - how a reply resolves to a course or section
is test_matching.py's job.
"""

from django.test import override_settings

from seat_signal.services import create_watch, get_watches_for_user
from seat_signal.utils import get_sem_str
from sms.models import ConversationState
from sms.tests.helpers import CURRENT_SEM_ID, SmsTestCase
from sms.views import (
    CAP_REACHED_MESSAGE,
    CONFIRM_RETRY_MESSAGE,
    EXIT_KEYWORDS,
    EXIT_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    OPT_IN_MESSAGE,
    SIGNAL_SET_MESSAGE,
    _confirm_prompt,
    _course_prompt,
    _section_prompt,
)


def label(code="CSCI 0320", section="S01", sem_id=CURRENT_SEM_ID):
    return f"{code} {section} ({get_sem_str(sem_id)})"


class CourseStepTests(SmsTestCase):
    def test_course_reply_stores_it_and_moves_to_awaiting_section(self):
        self.onboard()

        self.text("CSCI 0320")

        conversation_state = self.conversation_state()
        self.assertEqual(conversation_state.pending_code, "CSCI 0320")
        self.assertEqual(conversation_state.state, ConversationState.AWAITING_SECTION)
        self.assert_sent(_section_prompt(conversation_state))

    def test_pending_sem_id_is_pinned_at_the_course_step(self):
        self.onboard()

        self.text("CSCI 0320")

        self.assertEqual(self.conversation_state().pending_sem_id, CURRENT_SEM_ID)

    def test_exit_at_the_course_step_is_a_safe_reprompt(self):
        self.onboard()

        for keyword in EXIT_KEYWORDS:
            with self.subTest(keyword=keyword):
                self.text(keyword)

                self.assertEqual(
                    self.conversation_state().state, ConversationState.AWAITING_COURSE
                )
                self.assert_sent(f"{EXIT_MESSAGE} {_course_prompt()}")
                self.send_sms.reset_mock()

    def test_at_cap_a_course_reply_gets_the_cap_message_instead(self):
        self.onboard()
        create_watch(self.user(), self.sessions["CSCI 0320"])

        with override_settings(SIGNAL_CAP=1):
            self.text("CSCI 0330")

        self.assert_sent(CAP_REACHED_MESSAGE)
        self.assertEqual(self.conversation_state().pending_code, "")


class SectionStepTests(SmsTestCase):
    def setUp(self):
        super().setUp()
        self.onboard()
        self.set_state(ConversationState.AWAITING_SECTION, code="CSCI 0320")

    def test_section_reply_stores_it_and_moves_to_confirmation(self):
        self.text("S01")

        conversation_state = self.conversation_state()
        self.assertEqual(conversation_state.pending_section, "S01")
        self.assertEqual(conversation_state.state, ConversationState.AWAITING_CONFIRMATION)
        self.assert_sent(_confirm_prompt(conversation_state))

    def test_exit_returns_to_awaiting_course_without_creating_anything(self):
        for keyword in EXIT_KEYWORDS:
            with self.subTest(keyword=keyword):
                self.set_state(ConversationState.AWAITING_SECTION, code="CSCI 0320")

                self.text(keyword)

                self.assertEqual(
                    self.conversation_state().state, ConversationState.AWAITING_COURSE
                )
                self.assertFalse(get_watches_for_user(self.user()).exists())


class ConfirmationStepTests(SmsTestCase):
    def setUp(self):
        super().setUp()
        self.onboard()
        self.set_state(
            ConversationState.AWAITING_CONFIRMATION, code="CSCI 0320", section="S01"
        )

    def test_yes_creates_the_watch_and_confirms(self):
        self.text("YES")

        watches = list(get_watches_for_user(self.user()))
        self.assertEqual([w.session for w in watches], [self.sessions["CSCI 0320"]])
        self.assertEqual(self.conversation_state().state, ConversationState.AWAITING_COURSE)
        self.assert_sent(SIGNAL_SET_MESSAGE.format(session=label()))

    def test_yes_is_case_and_whitespace_insensitive(self):
        self.text("  yes ")

        self.assertTrue(get_watches_for_user(self.user()).exists())

    def test_unrecognized_reply_retries_without_creating_a_watch(self):
        self.text("maybe")

        self.assertFalse(get_watches_for_user(self.user()).exists())
        self.assertEqual(
            self.conversation_state().state, ConversationState.AWAITING_CONFIRMATION
        )
        self.assert_sent(CONFIRM_RETRY_MESSAGE)

    def test_exit_returns_to_awaiting_course_without_creating_anything(self):
        for keyword in EXIT_KEYWORDS:
            with self.subTest(keyword=keyword):
                self.set_state(
                    ConversationState.AWAITING_CONFIRMATION, code="CSCI 0320", section="S01"
                )

                self.text(keyword)

                self.assertEqual(
                    self.conversation_state().state, ConversationState.AWAITING_COURSE
                )
                self.assertFalse(get_watches_for_user(self.user()).exists())

    def test_confirming_the_same_course_twice_does_not_duplicate_the_watch(self):
        self.text("YES")
        self.set_state(
            ConversationState.AWAITING_CONFIRMATION, code="CSCI 0320", section="S01"
        )

        self.text("YES")

        self.assertEqual(get_watches_for_user(self.user()).count(), 1)

    def test_confirming_an_unmatched_course_section_combo_is_recovered_gracefully(self):
        # nothing validates pending_code/pending_section before this step yet, so
        # a combination with no matching CourseSession reaches the DB lookup -
        # the generic error handling around _handle_state_message (see views.py)
        # is what keeps that a clean reply instead of a 500
        self.set_state(
            ConversationState.AWAITING_CONFIRMATION, code="PHIL 9999", section="S99"
        )

        response = self.text("YES")

        self.assertEqual(response.status_code, 200)
        self.assert_sent(GENERIC_ERROR_MESSAGE)
        self.assertFalse(get_watches_for_user(self.user()).exists())


class CapTests(SmsTestCase):
    @override_settings(SIGNAL_CAP=1)
    def test_view_and_remove_still_work_at_cap(self):
        self.onboard()
        create_watch(self.user(), self.sessions["CSCI 0320"])

        self.text("VIEW")
        self.assertIn("CSCI 0320", self.last_sent())

        self.text("REMOVE")
        self.assertEqual(
            self.conversation_state().state, ConversationState.AWAITING_REMOVAL
        )

    @override_settings(SIGNAL_CAP=1)
    def test_cap_notice_is_appended_once_the_new_watch_fills_the_last_slot(self):
        self.onboard()
        self.set_state(
            ConversationState.AWAITING_CONFIRMATION, code="CSCI 0320", section="S01"
        )

        self.text("YES")

        self.assertIn(CAP_REACHED_MESSAGE, self.last_sent())

    @override_settings(SIGNAL_CAP=2)
    def test_no_cap_notice_while_still_under_the_cap(self):
        self.onboard()
        self.set_state(
            ConversationState.AWAITING_CONFIRMATION, code="CSCI 0320", section="S01"
        )

        self.text("YES")

        self.assertNotIn(CAP_REACHED_MESSAGE, self.last_sent())


class FullTranscriptTests(SmsTestCase):
    def test_cold_number_through_a_confirmed_watch(self):
        self.text("hello")
        self.text("CSCI 0320")
        self.text("S01")
        self.text("YES")

        conversation_state = self.conversation_state()
        self.assert_sent(
            OPT_IN_MESSAGE,
            _section_prompt(conversation_state),
            _confirm_prompt(conversation_state),
            SIGNAL_SET_MESSAGE.format(session=label()),
        )
        self.assertTrue(get_watches_for_user(self.user()).exists())
