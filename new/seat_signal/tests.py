import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import CourseSession, User
from seat_signal import utils
from seat_signal.utils import (
    CALENDAR_TIMEZONE,
    REGISTRATION_PERIODS,
    get_current_sem_id,
)
from seat_signal.services import SignalCapExceeded, create_watch, find_signals_with_open_seats
from seat_signal.signals import seat_opened


class SemesterUtilsTests(TestCase):
    """
    Winter/Spring belong to the *next* calendar year relative to the academic
    year encoded in a semester id. Easy off-by-one source, so it's pinned
    down here.
    """

    def test_sem_id_to_str_round_trip(self):
        cases = {
            "202410": "Fall 2024",
            "202415": "Winter 2025",  # academic year 2024 -> calendar year 2025
            "202420": "Spring 2025",  # same shift
            "202400": "Summer 2024",  # no shift
        }
        for sem_id, expected_str in cases.items():
            with self.subTest(sem_id=sem_id):
                self.assertEqual(utils.get_sem_str(sem_id), expected_str)
                self.assertEqual(utils.get_sem_id(expected_str), sem_id)

    def test_get_recent_sems_orders_chronologically(self):
        sem_ids = ["202410", "202415", "202420", "202300"]
        recent = utils.get_recent_sems(sem_ids, n=2)
        self.assertEqual([sem_id for sem_id, _ in recent], ["202420", "202415"])


class CreateWatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_num="+15551234567")
        self.sessions = [
            CourseSession.objects.create(
                crn=str(i), department_code="CSCI", course_code=f"0{i}",
                section="S01", sem_id="202410", title="Test",
            )
            for i in range(3)
        ]

    @override_settings(SIGNAL_CAP=2)
    def test_cap_enforced(self):
        create_watch(self.user, self.sessions[0])
        create_watch(self.user, self.sessions[1])
        with self.assertRaises(SignalCapExceeded):
            create_watch(self.user, self.sessions[2])


class SeatOpenedSignalTests(TestCase):
    """
    Nothing else proves find_signals_with_open_seats actually surfaces a
    watched session once seats open, or that seat_opened is receivable with
    the kwargs a listener (sms's receiver, see sms/signals.py) expects. C@B
    itself is mocked out so this never makes a live network call.

    sms's receiver is connected to this signal app-wide (via sms/apps.py's
    ready()), so send() below reaches it too, not just the listener this test
    connects - sms.telnyx_client.send_sms is mocked so that doesn't also
    place a real Telnyx call.
    """

    def setUp(self):
        self.user = User.objects.create_user(phone_num="+15559876543")
        self.session = CourseSession.objects.create(
            crn="99999", department_code="CSCI", course_code="0320",
            section="S01", sem_id="202410", title="Test",
        )
        create_watch(self.user, self.session)

    @patch("sms.signals.send_sms")
    @patch("seat_signal.services.check_seat_availability", return_value=1)
    def test_open_seat_is_surfaced_and_signal_is_receivable(
        self, mock_check_seat_availability, mock_send_sms
    ):
        results = list(find_signals_with_open_seats())
        self.assertEqual(results, [(self.session, [self.user])])

        received = []

        def on_seat_opened(sender, **kwargs):
            received.append(kwargs)

        seat_opened.connect(on_seat_opened)
        try:
            session, users = results[0]
            seat_opened.send(sender=self.__class__, user=users[0], session=session)
        finally:
            seat_opened.disconnect(on_seat_opened)

        self.assertEqual(received, [{"signal": seat_opened, "user": self.user, "session": self.session}])

def _at(year, month, day, hour=12, minute=0, tz=CALENDAR_TIMEZONE):
    """An aware UTC datetime for the given Eastern wall-clock moment."""
    return datetime.datetime(year, month, day, hour, minute, tzinfo=tz).astimezone(
        datetime.timezone.utc
    )


class GetCurrentSemIdTests(TestCase):
    def _sem_id_on(self, moment):
        with patch("seat_signal.utils.timezone.now", return_value=moment):
            return get_current_sem_id()

    def test_dates_inside_a_period_return_that_periods_sem_id(self):
        cases = [
            (_at(2026, 4, 1), "202600"),   # inside Summer 2026's first window
            (_at(2026, 4, 15), "202610"),  # inside Fall 2026 pre-registration
            (_at(2026, 11, 20), "202615"), # inside Winter 2027 (Wintersession)
            (_at(2027, 2, 1), "202620"),   # inside Spring 2027 add-deadline window
        ]
        for moment, expected in cases:
            with self.subTest(moment=moment):
                self.assertEqual(self._sem_id_on(moment), expected)

    def test_a_date_between_periods_returns_the_next_one_to_open(self):
        # 2026-04-10 is the day after Summer 2026's first window ends (4/9) and
        # before Fall 2026 pre-registration opens (4/14)
        self.assertEqual(self._sem_id_on(_at(2026, 4, 10)), "202610")

    def test_timezone_conversion_matters_at_a_period_boundary(self):
        # 11:30pm ET on the last day of a period is already the next UTC day -
        # a plain UTC date() would roll this over to the wrong period
        late_et = _at(2026, 4, 9, hour=23, minute=30)
        self.assertEqual(late_et.date(), datetime.date(2026, 4, 10))  # already tomorrow in UTC

        self.assertEqual(self._sem_id_on(late_et), "202600")

    def test_a_date_past_the_table_falls_back_to_the_last_period_and_logs(self):
        past_the_end = _at(2027, 5, 1)

        with self.assertLogs("seat_signal.utils", level="ERROR"):
            sem_id = self._sem_id_on(past_the_end)

        self.assertEqual(sem_id, REGISTRATION_PERIODS[-1][2])
