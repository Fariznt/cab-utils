from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import CourseSession, User
from seat_signal import utils
from seat_signal.services import SignalCapExceeded, create_watch, find_signals_with_open_seats
from seat_signal.signals import seat_opened


class SemesterUtilsTests(TestCase):
    """
    Winter/Spring belong to the *next* calendar year relative to the academic
    year encoded in a semester id — legacy's tasks.md flagged this exact shift
    as a recurring off-by-one source, so it's pinned down here.
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
            CourseSession.objects.create(crn=str(i), code=f"CSCI 0{i}", section="S01", sem_id="202410", title="Test")
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
    the kwargs a listener (sms's future receiver) would expect. C@B itself
    is mocked out so this never makes a live network call.
    """

    def setUp(self):
        self.user = User.objects.create_user(phone_num="+15559876543")
        self.session = CourseSession.objects.create(
            crn="99999", code="CSCI 0320", section="S01", sem_id="202410", title="Test"
        )
        create_watch(self.user, self.session)

    @patch("seat_signal.services.check_seat_availability", return_value=1)
    def test_open_seat_is_surfaced_and_signal_is_receivable(self, mock_check_seat_availability):
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
