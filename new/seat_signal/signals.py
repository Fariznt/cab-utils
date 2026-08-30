import django.dispatch

# Sent with kwargs user=<core.User>, session=<core.CourseSession> when a poll
# finds an open seat
seat_opened = django.dispatch.Signal()
