from django.db import models

from core.models import User


class ConversationState(models.Model):
    """Tracks where a user is in the SMS picking flow. One row per user."""

    AWAITING_COURSE = "awaiting_course"
    AWAITING_SECTION = "awaiting_section"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    STATE_CHOICES = [
        (AWAITING_COURSE, "Awaiting course"),
        (AWAITING_SECTION, "Awaiting section"),
        (AWAITING_CONFIRMATION, "Awaiting confirmation"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="conversation_state")
    state = models.CharField(max_length=32, choices=STATE_CHOICES, default=AWAITING_COURSE)
    # course/section picked so far, held until confirmed and turned into a SeatSignal
    pending_code = models.CharField(max_length=9, blank=True)
    pending_sem_id = models.CharField(max_length=6, blank=True)
    pending_section = models.CharField(max_length=3, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} @ {self.state}"


class OptInStatus(models.Model):
    """
    Whether a user wants texts at all. Checked before any messaging-state
    handling: if opted out, we don't respond except to a STOP/START keyword.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="opt_in_status")
    is_opted_in = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} ({'opted in' if self.is_opted_in else 'opted out'})"


class MessageHistory(models.Model):
    """Running list of messages exchanged between system and user. One row per user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="message_history")
    # each entry: {"direction": "inbound"|"outbound", "body": str, "at": iso timestamp}
    messages = models.JSONField(default=list)

    def __str__(self):
        return f"{self.user} ({len(self.messages)} messages)"
