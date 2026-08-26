import logging
import time

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import EventLog, User
from sms.models import ConversationState, MessageHistory, OptInStatus
from sms.telnyx_client import send_sms

logger = logging.getLogger(__name__)

START_KEYWORD = "START"
HELP_KEYWORD = "HELP"
STOP_KEYWORDS = ["STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]

OPT_IN_MESSAGE = (
    "Seat Signal: Hello! We'll help you watch a course section and contact you "
    "the moment a seat opens. Msg frequency may vary. Msg&data rates may apply. "
    "Reply HELP for options, STOP to opt out. Terms & Privacy at "
    "https://seatsignal.fariz.cc/#privacy. What course would you like to watch for seats?"
)
OPT_OUT_MESSAGE = (
    "Seat Signal: You are unsubscribed and will receive no further messages. "
    "Reply START to resubscribe."
)
HELP_MESSAGE = (
    "Seat Signal: Reply STOP to unsubscribe. For other help, reach out through "
    "https://bit.ly/4ik1eEZ."
)

RESTART_MESSAGE = (
    "Restarting the course picking flow. What course would you like to watch for seats?"
)

# message.finalized error codes that will not succeed on retry.
PERMANENT_ERROR_CODES = {"40001", "47000"}
RETRY_TAG = "retry"
RETRY_DELAY_SECONDS = 2


def _send(user, to_number, text, tags=None):
    """Sends a text and logs it to the shared event log in one step."""
    send_sms(to_number, text, tags=tags)
    EventLog.objects.create(event_type="sms_sent", user=user, message=text)


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
          try:
            user = User.objects.get(phone_num=from_number)
            created = False
          except User.DoesNotExist:
            user = User.objects.create_user(phone_num=from_number)
            created = True

          if created: # set up initial state for user & send initial message
            OptInStatus.objects.create(user=user)
            ConversationState.objects.create(user=user)
            EventLog.objects.create(event_type="account_created", user=user, message=None)

            _send(user, from_number, OPT_IN_MESSAGE)

          # append message to user's message history
          history, _ = MessageHistory.objects.get_or_create(user=user)
          history.messages.append({"direction": "inbound", "body": text, "at": received_at})
          history.save()
          EventLog.objects.create(event_type="sms_received", user=user, message=text)

          if not created: 
            # opt-in/opt-out gating sits above messaging state
            opt_in_status = user.opt_in_status
            keyword = (text or "").strip().upper()

            if keyword in STOP_KEYWORDS:
              opt_in_status.is_opted_in = False
              opt_in_status.save()
              _send(user, from_number, OPT_OUT_MESSAGE)
            elif not opt_in_status.is_opted_in:
              if keyword == START_KEYWORD:
                opt_in_status.is_opted_in = True
                opt_in_status.save()
                user.conversation_state.state = ConversationState.AWAITING_COURSE
                user.conversation_state.save()
                _send(user, from_number, OPT_IN_MESSAGE)
              # else: opted out and not a START, stay silent
            else:
              _handle_state_message(user, text)

        elif event_type == "message.finalized": # a send was finalized
          errors = message.get("errors") or []
          if errors:
            error_code = str(errors[0].get("code"))
            EventLog.objects.create(
                event_type="error",
                message=f"send to {to_numbers} failed: {error_code}",
                metadata={"message_id": message_id, "errors": errors},
            )

            already_retried = RETRY_TAG in (message.get("tags") or [])
            if error_code not in PERMANENT_ERROR_CODES and not already_retried:
              time.sleep(RETRY_DELAY_SECONDS)
              send_sms(to_numbers[0], text, tags=[RETRY_TAG])

        return Response(status=200)


def _handle_state_message(user, text):
    # if the user said HELP, send the help message defined with a small time delay after (so official hepl message goes first)
    # and set a NEEDS_HELP = True
    # if this flag is true, for each conditioned user state our 
    # next question should include a tailored but brief help message
    # for this state specifically (mention restart as an option, and a more thorough explanation of whats
    # happening in this state in the context of the app). you dont have to worry about exactly
    # how these are defined, just come up with something and we will change later



    # if user state is awaiting_course
      # if NEEDS_HELP ...
      # else
        # if the text says RESTART or NO set state to awaiting_course
        # and send RESTART_MESSAGE
        # but otherwise call a helper function (dont implement it, just make empty body function again)
        # that will handle the user's course selection text which might or might not be formatted
        # save that course selection to user message state
    # if user state is awaiting_section
      # if NEEDS_HELP ...
      # else
        # if the text says RESTART or NO set state to awaiting_course
        # and send RESTART_MESSAGE
        # but otherwise call a helper function (dont implement it, just make empty body function again)
        # that will handle the user's session selection text which might or might not be formatted
        # save that session selection to user message state
    # if user state is awaiting_confirmation
      # if NEEDS_HELP ...
      # else
        # if the text says RESTART or NO set state to awaiting_course
        # and send RESTART_MESSAGE
        # but if the text says YES then set a seat signal for the course and user
        # and set state to awaiting_course
        # but if the text says anything else, ask the user to confirm again


    pass
