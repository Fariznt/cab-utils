from django.urls import path

from sms.views import TelnyxWebhook

app_name = "sms"

urlpatterns = [
    path("webhook/", TelnyxWebhook.as_view(), name="telnyx-webhook"),
]
