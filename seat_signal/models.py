from django.db import models

from core.models import CourseSession, User


class SeatSignal(models.Model):
    """Represents a User watching a specific CourseSession for an open seat."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_signals")
    session = models.ForeignKey(CourseSession, on_delete=models.PROTECT, related_name="session_signals")
    datetime_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "session"], name="unique_user_session_signal"),
        ]

    def __str__(self):
        return f"{self.user} watching {self.session}"


class Heartbeat(models.Model):
    """
    Liveness for long-running processes in this app (just the poll loop today).
    One row per process, updated in place instead of appended to, so it costs
    the same storage whether it ticks once a day or every ten seconds - which a
    log line per poll cycle did not. Read by the /healthz/ endpoint (see
    CAB_Utils/urls.py).
    """
    # The only process with a heartbeat today; a constant so the writer
    # (poll_seats) and the reader (/healthz/) can't drift.
    POLL_SEATS = "poll_seats"

    name = models.CharField(max_length=32, primary_key=True)
    last_seen = models.DateTimeField()

    def __str__(self):
        return f"{self.name} @ {self.last_seen:%Y-%m-%d %H:%M:%S}"
