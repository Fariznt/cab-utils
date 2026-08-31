"""
The seat_opened receiver is the only thing connecting seat_signal's polling
loop to an actual outbound text (see sms/signals.py) - registered via
sms/apps.py's ready(), so it's live on every seat_opened.send() without any
per-test wiring.
"""

from unittest.mock import patch

from django.test import TestCase

from core.models import CourseSession, EventLog, User
from seat_signal.signals import seat_opened

USER_NUMBER = "+15551234567"


class SeatOpenedReceiverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_num=USER_NUMBER)
        self.session = CourseSession.objects.create(
            crn="99999", code="CSCI 0320", section="S01", sem_id="202410", title="Test"
        )
        send_patcher = patch("sms.signals.send_sms")
        self.send_sms = send_patcher.start()
        self.addCleanup(send_patcher.stop)

    def test_sends_a_text_naming_the_session(self):
        seat_opened.send(sender=self.__class__, user=self.user, session=self.session)

        self.send_sms.assert_called_once()
        user, to_number, text = self.send_sms.call_args.args
        self.assertEqual(user, self.user)
        self.assertEqual(to_number, self.user.phone_num)
        self.assertIn("CSCI 0320 S01", text)

    def test_a_failed_send_is_logged_instead_of_raised(self):
        self.send_sms.side_effect = RuntimeError("telnyx down")

        seat_opened.send(sender=self.__class__, user=self.user, session=self.session)

        self.assertTrue(
            EventLog.objects.filter(
                event_type="error", user=self.user, session=self.session
            ).exists()
        )
