from django.urls import path

from sms.views import TelnyxWebhookView

app_name = "sms"

urlpatterns = [
    path("webhook/", TelnyxWebhookView.as_view(), name="telnyx-webhook"),
]
