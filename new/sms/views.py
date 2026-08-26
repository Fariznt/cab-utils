import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from sms.telnyx_client import send_sms

logger = logging.getLogger(__name__)


class TelnyxWebhookView(APIView):

    permission_classes = [AllowAny]  # Telnyx, not a Django user

    def post(self, request):
        data = request.data.get("data", {})
        event_type = data.get("event_type")
        message = data.get("payload", {})
        
        from_number = message.get("from", {}).get("phone_number")
        to_numbers = [t.get("phone_number") for t in message.get("to", [])]
        text = message.get("text")
        received_at = message.get("received_at")
        message_id = message.get("id")

        logger.info(f"event_type={event_type} from={from_number} text={text!r}")

        # TODO: handle it

        return Response(status=200)
