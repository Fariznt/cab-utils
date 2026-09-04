import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import EventLog

# Every EventLog row is mirrored onto this logger, so the level-gated handlers
# in settings.py (app.log for everything, review.log for >= REVIEW_THRESHOLD)
# are the single place routing is decided. Call sites just write the row.
events_logger = logging.getLogger("cab_utils.events")


@receiver(post_save, sender=EventLog)
def log_event(sender, instance, created, **kwargs):
    if not created:
        return

    # Context the message may not carry on its own - account_created, for one,
    # writes no message at all - so no review.log line is anonymous.
    parts = [instance.message or instance.event_type]
    if instance.user_id:
        parts.append(f"user={instance.user_id}")
    if instance.session_id:
        parts.append(f"session={instance.session_id}")
    text = " ".join(parts)
    level = getattr(logging, instance.level)

    # on_commit rather than logging right here: post_save fires before the
    # enclosing transaction commits, so a later rollback would otherwise leave
    # a log line claiming an event that never persisted. Outside a transaction
    # this runs immediately.
    transaction.on_commit(lambda: events_logger.log(level, text))
