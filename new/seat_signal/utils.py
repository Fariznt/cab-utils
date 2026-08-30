"""
Semester-id conversions. Ported verbatim from legacy/seat_signal/utils.py — this
is reverse-engineered domain knowledge about C@B, not implementation choice.

Semester id = 4-digit academic-year start year + 2-digit term code
('15'=Winter, '20'=Spring, '00'=Summer, '10'=Fall). Winter/Spring belong to the
*second* calendar year of the academic year (e.g. '202415' = Winter, calendar
year 2025) — a recurring source of off-by-one bugs, so this logic is pinned
down by tests in seat_signal/tests.py.
"""

import datetime
import logging
from zoneinfo import ZoneInfo

from django.utils import timezone

logger = logging.getLogger(__name__)

TERM_NAMES = {
    "15": "Winter",
    "20": "Spring",
    "00": "Summer",
    "10": "Fall",
}
TERM_IDS = {name: code for code, name in TERM_NAMES.items()}
TERM_RANK = {"15": 0, "20": 1, "00": 2, "10": 3}
SHIFTED_TERMS = {"15", "20"}  # Winter, Spring (by term code)
SHIFTED_TERM_NAMES = {"Winter", "Spring"}  # same, by term name


def get_recent_sems(sem_ids: list[str], n: int = 4) -> list[tuple[str, str]]:
    """Takes a list of semester ids and returns the n most recent as (id, readable name) tuples."""

    def sort_key(sem_id: str):
        academic_year = int(sem_id[:4])
        term = sem_id[4:]
        calendar_year = academic_year + 1 if term in SHIFTED_TERMS else academic_year
        return (calendar_year, TERM_RANK[term])

    recent_ids = sorted(sem_ids, key=sort_key, reverse=True)[:n]
    return [(sem_id, get_sem_str(sem_id)) for sem_id in recent_ids]


def get_sem_str(sem_id: str) -> str:
    """Converts a semester id (e.g. '202510') to a readable string (e.g. 'Fall 2025')."""
    academic_year = int(sem_id[:4])
    term_code = sem_id[4:]
    term = TERM_NAMES[term_code]
    year = academic_year + 1 if term_code in SHIFTED_TERMS else academic_year
    return f"{term} {year}"


def get_sem_id(sem_str: str) -> str:
    """Converts a readable semester string (e.g. 'Fall 2025') to a semester id."""
    term, year = sem_str.split()
    year = int(year)
    term_id = TERM_IDS[term]
    academic_year = year - 1 if term in SHIFTED_TERM_NAMES else year
    return f"{academic_year}{term_id}"


# ACADEMIC CALENDAR CONSTANTS =====================================================================

CALENDAR_TIMEZONE = ZoneInfo("America/New_York")

# Undergraduate course-registration windows for the 2026-2027 academic year, as
# (start, end, sem_id), taken from Brown's registrar calendar. Must stay sorted
# by start and non-overlapping - get_current_sem_id relies on both. The
# in-semester windows run through the last day to add a course, since that's
# when watching for an open seat stops being useful.
# This constant needs an update every academic year as registration period dates are released
REGISTRATION_PERIODS = (
    (datetime.date(2026, 3, 30), datetime.date(2026, 4, 9), "202600"),    # Summer 2026
    (datetime.date(2026, 4, 14), datetime.date(2026, 4, 21), "202610"),   # Fall 2026 pre-registration
    (datetime.date(2026, 4, 22), datetime.date(2026, 6, 17), "202600"),   # Summer 2026 re-opens, through last day to change courses (no distinct add-with-fee deadline for Summer)
    (datetime.date(2026, 9, 4), datetime.date(2026, 10, 6), "202610"),    # Fall 2026 through add deadline
    (datetime.date(2026, 11, 10), datetime.date(2026, 11, 17), "202620"), # Spring 2027 pre-registration
    (datetime.date(2026, 11, 18), datetime.date(2026, 12, 16), "202615"), # Winter 2027 (Wintersession)
    (datetime.date(2027, 1, 22), datetime.date(2027, 2, 24), "202620"),   # Spring 2027 through add deadline
    (datetime.date(2027, 4, 19), datetime.date(2027, 4, 27), "202710"),   # Fall 2027 pre-registration
)


def get_current_sem_id():
    """
    Returns the semester the picking flow scopes to - never asked for, always
    automatic. It's the semester of the registration period we're currently in,
    or if we're between periods, of the next one to open.
    """
    # Brown's calendar is Eastern; settings.TIME_ZONE is UTC, so a plain
    # localdate() would roll over to tomorrow after 8pm ET.
    today = timezone.now().astimezone(CALENDAR_TIMEZONE).date()

    # Periods are sorted and non-overlapping, so the first one that hasn't ended
    # is either the one we're in or the next one to open - both are the semester
    # we want, so no separate lookahead pass is needed.
    for _, end, sem_id in REGISTRATION_PERIODS:
        if today <= end:
            return sem_id

    # Ran off the end of the table - the calendar needs the next academic year added.
    logger.error(f"No registration period covers {today}, REGISTRATION_PERIODS needs updating")
    return REGISTRATION_PERIODS[-1][2]
