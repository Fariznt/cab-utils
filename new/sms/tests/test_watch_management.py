"""
VIEW and REMOVE, both reachable from the default awaiting_course state (see
CapTests in test_picking_flow.py for why they sit above the cap check).
"""

from django.test import override_settings

from seat_signal.services import create_watch, get_watches_for_user
from sms.models import ConversationState
from sms.tests.helpers import SmsTestCase
from sms.views import (
    NO_WATCHES_MESSAGE,
    REMOVAL_RETRY_MESSAGE,
    REMOVE_PROMPT,
    WATCH_REMOVED_MESSAGE,
    _numbered_watches,
    _session_label,
    watch_list_message,
)


class ViewTests(SmsTestCase):
    def test_view_with_no_watches(self):
        self.onboard()

        self.text("VIEW")

        self.assert_sent(NO_WATCHES_MESSAGE)
        self.assertEqual(self.conversation_state().state, ConversationState.AWAITING_COURSE)

    def test_view_lists_watches_in_creation_order(self):
        user = self.onboard()
        # created out of order, so a naive default ordering couldn't pass this
        create_watch(user, self.sessions["MATH 0100"])
        create_watch(user, self.sessions["CSCI 0320"])

        self.text("VIEW")

        watches = list(get_watches_for_user(user).order_by("datetime_created"))
        expected = watch_list_message(watches)
        self.assert_sent(expected)
        self.assertIn("1. MATH 0100", expected)
        self.assertIn("2. CSCI 0320", expected)


class RemoveTests(SmsTestCase):
    def test_remove_with_no_watches_does_not_strand_the_user(self):
        self.onboard()

        self.text("REMOVE")

        self.assert_sent(NO_WATCHES_MESSAGE)
        self.assertEqual(self.conversation_state().state, ConversationState.AWAITING_COURSE)

    def test_remove_lists_watches_and_enters_awaiting_removal(self):
        user = self.onboard()
        create_watch(user, self.sessions["CSCI 0320"])

        self.text("REMOVE")

        watches = list(get_watches_for_user(user).order_by("datetime_created"))
        self.assert_sent(f"{_numbered_watches(watches)}\n{REMOVE_PROMPT}")
        self.assertEqual(
            self.conversation_state().state, ConversationState.AWAITING_REMOVAL
        )

    def test_choosing_a_number_removes_that_specific_watch(self):
        user = self.onboard()
        create_watch(user, self.sessions["CSCI 0320"])
        create_watch(user, self.sessions["MATH 0100"])
        self.text("REMOVE")

        self.text("2")

        remaining = list(get_watches_for_user(user))
        self.assertEqual([w.session for w in remaining], [self.sessions["CSCI 0320"]])
        self.assertEqual(self.conversation_state().state, ConversationState.AWAITING_COURSE)
        self.assertEqual(
            self.last_sent(),
            WATCH_REMOVED_MESSAGE.format(session=_session_label(self.sessions["MATH 0100"])),
        )

    def test_out_of_range_number_retries_without_removing_anything(self):
        user = self.onboard()
        create_watch(user, self.sessions["CSCI 0320"])
        self.text("REMOVE")

        for choice in ["0", "9"]:
            with self.subTest(choice=choice):
                self.text(choice)

                self.assertTrue(get_watches_for_user(user).exists())
                self.assertEqual(
                    self.conversation_state().state, ConversationState.AWAITING_REMOVAL
                )

    def test_non_numeric_reply_retries(self):
        user = self.onboard()
        create_watch(user, self.sessions["CSCI 0320"])
        self.text("REMOVE")

        self.text("the first one")

        self.assertTrue(get_watches_for_user(user).exists())
        self.assertIn(REMOVAL_RETRY_MESSAGE, self.sent())

    def test_exit_cancels_without_removing_anything(self):
        user = self.onboard()
        create_watch(user, self.sessions["CSCI 0320"])
        self.text("REMOVE")

        self.text("EXIT")

        self.assertTrue(get_watches_for_user(user).exists())
        self.assertEqual(self.conversation_state().state, ConversationState.AWAITING_COURSE)

    def test_a_watch_vanishing_before_the_reply_does_not_crash(self):
        # mirrors the poll loop deleting a SeatSignal out from under the user
        # between the REMOVE list being sent and their reply
        user = self.onboard()
        create_watch(user, self.sessions["CSCI 0320"])
        self.text("REMOVE")
        get_watches_for_user(user).delete()

        response = self.text("1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.conversation_state().state, ConversationState.AWAITING_REMOVAL
        )
        self.assertIn(REMOVAL_RETRY_MESSAGE, self.sent())

    def test_removing_frees_a_capped_slot(self):
        with override_settings(SIGNAL_CAP=1):
            user = self.onboard()
            create_watch(user, self.sessions["CSCI 0320"])

            self.text("REMOVE")
            self.text("1")
            self.set_state(
                ConversationState.AWAITING_CONFIRMATION, code="MATH 0100", section="S01"
            )
            self.text("YES")

            watches = list(get_watches_for_user(user))
            self.assertEqual([w.session for w in watches], [self.sessions["MATH 0100"]])
