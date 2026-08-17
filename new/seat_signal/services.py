import logging

import requests
from django.conf import settings

from core.models import CourseSession, EventLog, User
from seat_signal.models import SeatSignal

logger = logging.getLogger(__name__)

# Same reverse-engineered C@B endpoint/UA as legacy's enable_ss.py — required
# for C@B's API to respond normally, see legacy_overview.md.
DETAILS_URL = "https://cab.brown.edu/api/?page=fose&route=details"
SPOOFED_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 "
        "Safari/537.36"
    ),
}


class SignalCapExceeded(Exception):
    """Raised when a user tries to watch more sessions than settings.SIGNAL_CAP."""


def create_watch(user: User, session: CourseSession) -> SeatSignal:
    """
    Creates a SeatSignal watch. Enforces SIGNAL_CAP server-side — critical
    since each watch is a future SMS send, not just a UX limit (same invariant
    legacy's watch_course view enforced, now living in domain logic instead).
    """
    active_count = SeatSignal.objects.filter(user=user).count()
    if active_count >= settings.SIGNAL_CAP:
        raise SignalCapExceeded(f"User already has {active_count} active signals (cap: {settings.SIGNAL_CAP})")

    watch, created = SeatSignal.objects.get_or_create(user=user, session=session)
    if created:
        EventLog.objects.create(
            event_type="watch_created", user=user, session=session,
            message=f"Watch created for {session}",
        )
    return watch


def remove_watch(user: User, session: CourseSession) -> bool:
    """Deletes a SeatSignal watch. Returns whether a row was actually deleted."""
    deleted, _ = SeatSignal.objects.filter(user=user, session=session).delete()
    if deleted:
        EventLog.objects.create(
            event_type="watch_removed", user=user, session=session,
            message=f"Watch removed for {session}",
        )
    return bool(deleted)


def get_watches_for_user(user: User):
    return SeatSignal.objects.filter(user=user).select_related("session")


def check_seat_availability(session: CourseSession) -> int:
    """
    Hits C@B's details endpoint and returns the open seat count. C@B has no
    plain numeric seats field — the count is embedded in an HTML fragment, so
    it's scraped by string-partition (ported from legacy's enable_ss.py).
    """
    payload = {"key": f"crn:{session.crn}"}
    response = requests.post(DETAILS_URL, json=payload, headers=SPOOFED_HEADERS)
    response.raise_for_status()
    course_details = response.json()

    seats_string = course_details["seats"].partition('<span class="seats_avail">')[2].partition("</span>")[0]
    return int(seats_string)


def get_sessions_with_active_signals():
    return CourseSession.objects.filter(session_signals__isnull=False).distinct()


def find_signals_with_open_seats():
    """
    Checks every CourseSession with an active watch and yields (session, users)
    for the ones that currently have an open seat. Isolates one bad course's
    failure (bad response, C@B format change, etc.) from the rest of the pass —
    legacy wrapped the *entire* poll pass in one try/except, so a single bad
    course aborted checking everything after it.
    """
    for session in get_sessions_with_active_signals():
        try:
            seat_count = check_seat_availability(session)
        except Exception:
            logger.exception(f"Failed to check seat availability for {session}")
            continue
        if seat_count > 0:
            users = list(User.objects.filter(user_signals__session=session))
            yield session, users
