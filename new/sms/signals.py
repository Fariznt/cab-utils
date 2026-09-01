"""
Connects seat_signal's seat_opened signal to the actual outbound text. Wired
up by sms/apps.py's ready() - importing this module is what registers the
receiver below with Django's signal dispatcher.
"""

import logging

from django.dispatch import receiver

from core.models import EventLog
from seat_signal.signals import seat_opened
from sms.conversation import SEAT_OPENED_MESSAGE, _session_label_no_sem
from sms.telnyx_client import send_sms

logger = logging.getLogger(__name__)


@receiver(seat_opened)
def send_seat_opened_text(sender, user, session, **kwargs):
    # Signals run synchronously in the sender's call stack (poll_seats.py), so
    # an unhandled exception here would propagate back into the poll loop and
    # abort the rest of that pass - the same per-user isolation the loop
    # already has around each course check.
    try:
        text = SEAT_OPENED_MESSAGE.format(session=_session_label_no_sem(session))
        send_sms(user, user.phone_num, text)
    except Exception:
        logger.exception(f"Failed to send seat_opened text for user {user.pk}")
        EventLog.objects.create(
            event_type="error", user=user, session=session,
            message="Failed to send seat_opened notification",
        )
