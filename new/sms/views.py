import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from sms.telnyx_client import send_sms

logger = logging.getLogger(__name__)

# TODO: add constants for the stop and help messages described in
# telnyx-campaign-form.md, and list consatnts for stop, help, and start keywords. 
# most will be singletons except stop keyword list.
# we will reuse this across our handling of help/stop across the various messaging states

class TelnyxWebhookView(APIView):

    permission_classes = [AllowAny]  # Telnyx, not a Django user. auth via Telnyx-provided info

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

        if event_type == "message.received": # a client message was received
          # TODO: if this is a user we have not seen before, add them.
          # so they are added as an opted in user, number saved to user, 
          # messaging state set to the default state described in models.py 

          # append message to the user's message history

          # if the user is one we've seen before, call helper function
          # that passes user state and message to be processed  
        elif event_type == "message.finalized": # a send was finalized
          # log the error with failure type. if its permanent (ex 40001 invalid number, 47000 no dlc campaign),
          # dont try again. otherwise try again with a short fixed delay of 2 seconds
          # we can encode only one try by working with the tags field to encode whether a message
          # attempt was a second try. youll need to add tags to this post handler



        return Response(status=200)
