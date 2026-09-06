import logging

import requests
from django.conf import settings

from core.models import CourseSession, EventLog, User
from seat_signal.models import SeatSignal

logger = logging.getLogger(__name__)

# Reverse-engineered C@B details endpoint; needs a browser User-Agent to respond normally.
DETAILS_URL = "https://cab.brown.edu/api/?page=fose&route=details"
SPOOFED_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 "
        "Safari/537.36"
    ),
}


# Consecutive check failures across poll passes, reset by any success. A
# persistent failure (C@B changing its response shape, say) would otherwise log
# an error every cycle forever, and each of those is a billed alert SMS once
# CloudWatch alerting is wired up. Past settings.POLL_ERROR_LIMIT the loop exits
# and lets systemd restart it, alerting once instead of on a loop.
_consecutive_failures = 0


class SignalCapExceeded(Exception):
    """Raised when a user tries to watch more sessions than settings.SIGNAL_CAP."""


def create_watch(user: User, session: CourseSession) -> SeatSignal:
    """
    Creates a SeatSignal watch. Enforces SIGNAL_CAP server-side since each
    watch is a future SMS send, not just a UX limit.
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
        if not user.has_created_watch:
            user.has_created_watch = True
            user.save(update_fields=["has_created_watch"])
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
    return SeatSignal.objects.filter(user=user).select_related("session").order_by("datetime_created")


def check_seat_availability(session: CourseSession) -> int | None:
    """
    Hits C@B's details endpoint and returns the open seat count, or None if
    C@B reports no seat count at all for this section. That's not an error:
    permission-based sections (independent studies, directed research, and
    reportedly others depending on the term) genuinely have no numeric cap,
    so "undefined" is the correct value, not 0 or an exception.
    """
    payload = {"key": f"crn:{session.crn}"}
    response = requests.post(DETAILS_URL, json=payload, headers=SPOOFED_HEADERS, timeout=(5, 15))
    response.raise_for_status()
    course_details = response.json()

    seats_html = course_details["seats"]
    if not seats_html:
        return None
    seats_string = seats_html.partition('<span class="seats_avail">')[2].partition("</span>")[0]
    return int(seats_string)


def course_is_uncapped(code: str, sem_id: str) -> bool:
    """
    True only if every current section of this course has no seat count at
    all. Checked live against C@B rather than inferred from any course
    metadata (e.g. schedule type) - which sections work this way isn't stable
    enough to hardcode, and used to include sections beyond independent
    study/directed research.
    """
    sessions = list(CourseSession.objects.filter(code=code, sem_id=sem_id))
    return bool(sessions) and all(check_seat_availability(s) is None for s in sessions)


def get_sessions_with_active_signals():
    return CourseSession.objects.filter(session_signals__isnull=False).distinct()


def find_signals_with_open_seats():
    """
    Checks every CourseSession with an active watch and yields (session, users)
    for the ones that currently have an open seat. Isolates one bad course's
    failure (bad response, C@B format change, etc.) from the rest of the pass,
    so a single bad course doesn't abort checking everything after it.
    """
    global _consecutive_failures

    for session in get_sessions_with_active_signals():
        try:
            seat_count = check_seat_availability(session)
        except Exception:
            logger.exception(f"Failed to check seat availability for {session}")
            EventLog.objects.create(
                event_type="error", level="ERROR", session=session,
                message=f"Failed to check seat availability for {session}",
            )
            _consecutive_failures += 1
            if _consecutive_failures >= settings.POLL_ERROR_LIMIT:
                message = f"Poll loop shutting down after {_consecutive_failures} consecutive seat-check failures"
                logger.critical(message)
                EventLog.objects.create(event_type="error", level="CRITICAL", message=message)
                raise SystemExit(1)
            continue

        _consecutive_failures = 0
        if seat_count is not None and seat_count > 0:
            users = list(User.objects.filter(user_signals__session=session))
            yield session, users
