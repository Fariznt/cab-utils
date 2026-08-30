"""
_get_current_sem_id: which semester the picking flow scopes to, resolved from
REGISTRATION_PERIODS and today's date - never asked of the user, so wrong here
means every course lookup that semester is silently wrong too.
"""

import datetime
from unittest.mock import patch

from django.test import TestCase

from sms.views import CALENDAR_TIMEZONE, REGISTRATION_PERIODS, _get_current_sem_id


def _at(year, month, day, hour=12, minute=0, tz=CALENDAR_TIMEZONE):
    """An aware UTC datetime for the given Eastern wall-clock moment."""
    return datetime.datetime(year, month, day, hour, minute, tzinfo=tz).astimezone(
        datetime.timezone.utc
    )


class GetCurrentSemIdTests(TestCase):
    def _sem_id_on(self, moment):
        with patch("sms.views.timezone.now", return_value=moment):
            return _get_current_sem_id()

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

        with self.assertLogs("sms.views", level="ERROR"):
            sem_id = self._sem_id_on(past_the_end)

        self.assertEqual(sem_id, REGISTRATION_PERIODS[-1][2])
