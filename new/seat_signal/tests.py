from django.test import TestCase, override_settings

from core.models import CourseSession, User
from seat_signal import utils
from seat_signal.services import SignalCapExceeded, create_watch


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
