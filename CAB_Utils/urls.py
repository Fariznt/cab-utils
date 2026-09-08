from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from sms.views import TelnyxStatusWebhook

urlpatterns = [
    path("admin/", admin.site.urls),
    # Liveness check only, returns 200 OK
    path("healthz/", lambda request: HttpResponse("ok"), name="healthz"),
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
