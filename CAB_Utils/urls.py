import datetime

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.utils import timezone

from seat_signal.models import Heartbeat
from sms.views import TelnyxStatusWebhook

# How stale the poll loop's heartbeat can get before healthz calls it dead. 
POLL_MAX_AGE = datetime.timedelta(minutes=5)


def healthz(request):
    """
    Liveness for the web process and the poll loop both
    """
    last_seen = (
        Heartbeat.objects.filter(name=Heartbeat.POLL_SEATS)
        .values_list("last_seen", flat=True)
        .first()
    )
    # No row at all means no pass has ever completed, which isn't healthy either.
    poll_alive = last_seen is not None and timezone.now() - last_seen < POLL_MAX_AGE
    return JsonResponse(
        {"status": "ok" if poll_alive else "degraded", "poll_seats_last_seen": last_seen},
        status=200 if poll_alive else 503,
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("sms/", include("sms.urls")),
    path("ops/", include("ops.urls")),
    # Lives outside the sms prefix because the URL is fixed in Telnyx's 10DLC
    # campaign config, not chosen here.
    path(
        "webhooks/telnyx/status-update/",
        TelnyxStatusWebhook.as_view(),
        name="telnyx-status-update",
    ),
]
