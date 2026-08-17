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
