import django.dispatch

# Sent with kwargs user=<core.User>, session=<core.CourseSession> when a poll
# finds an open seat. seat_signal doesn't know or care who's listening — sms
# connects a receiver (via sms/apps.py's ready()) once it exists.
seat_opened = django.dispatch.Signal()
