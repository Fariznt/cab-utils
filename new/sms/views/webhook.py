"""
The Telnyx webhook itself: verifies the caller, routes the event, and owns
everything that happens around the conversation - creating a user on first
contact, the opt-in/opt-out gate, and retrying a failed send.

The conversation itself lives in inbound_state_handler.py; this module decides
whether we get that far.
"""

import logging
import time

from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import EventLog, User
from sms.conversation import (
    GENERIC_ERROR_MESSAGE,
    HELP_FOLLOWUP_DELAY_SECONDS,
    HELP_KEYWORD,
    HELP_MESSAGE,
    OPT_IN_MESSAGE,
    OPT_OUT_MESSAGE,
    START_KEYWORD,
    STOP_KEYWORDS,
)
from sms.models import ConversationState, MessageHistory, OptInStatus
from sms.telnyx_client import send_sms
from sms.views.auth import TelnyxSignature
from sms.views.inbound_state_handler import _handle_state_message

logger = logging.getLogger(__name__)

# message.finalized error codes that will not succeed on retry.
PERMANENT_ERROR_CODES = {"40001", "47000"}
RETRY_TAG = "retry"
RETRY_DELAY_SECONDS = 2


class TelnyxWebhook(APIView):
    """
    Handles Telnyx (CPaaS providers) webhooks for inbound and outbound messages. 
    """

    # The caller is Telnyx, not a Django user, so no authentication backend
    # applies - the signature check is the whole of this endpoint's auth.
    authentication_classes = []
    permission_classes = [TelnyxSignature]

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

          if created: # set up initial state for user
            opt_in_status = OptInStatus.objects.create(user=user)
            ConversationState.objects.create(user=user)
            EventLog.objects.create(event_type="account_created", user=user, message=None)
          else:
            opt_in_status = user.opt_in_status

          # append message to user's message history
          history, _ = MessageHistory.objects.get_or_create(user=user)
          history.messages.append({"direction": "inbound", "body": text, "at": received_at})
          history.save()
          EventLog.objects.create(event_type="sms_received", user=user, message=text)

          keyword = (text or "").strip().upper()

          # HELP sits above every other branch, including the opt-in gate: carriers
          # require it to be answered for anyone who asks, opted out or not. The
          # tailored per-state help follows from _handle_state_message after a beat.
          if keyword == HELP_KEYWORD:
            send_sms(user, from_number, HELP_MESSAGE)
            time.sleep(HELP_FOLLOWUP_DELAY_SECONDS)

          # opt-in/opt-out gating sits above messaging state. STOP is handled the
          # same for a brand-new number as for a known one: a cold number whose
          # first word is STOP is opting out, not signing up, and answering that
          # with the marketing greeting would be a violation.
          if keyword in STOP_KEYWORDS:
            opt_in_status.is_opted_in = False
            opt_in_status.save()
            send_sms(user, from_number, OPT_OUT_MESSAGE)
          elif created:
            # first contact is a greeting only - their message isn't a course yet
            send_sms(user, from_number, OPT_IN_MESSAGE)
          elif not opt_in_status.is_opted_in:
            if keyword == START_KEYWORD:
              opt_in_status.is_opted_in = True
              opt_in_status.save()
              user.conversation_state.state = ConversationState.AWAITING_COURSE
              user.conversation_state.save()
              send_sms(user, from_number, OPT_IN_MESSAGE)
            # else: opted out and not a START, stay silent
          else:
            # The conversation flow is where the unanticipated failures live (a
            # course that vanished mid-conversation, a C@B format change). Telnyx
            # gets its 200 either way; the user gets told rather than ignored.
            #
            # _handle_state_message runs in its own savepoint so a failure partway
            # through (e.g. a bad write) rolls back just its own writes, rather
            # than poisoning the rest of this transaction and taking the recovery
            # writes below down with it.
            try:
              with transaction.atomic():
                _handle_state_message(user, text)
            except Exception:
              logger.exception(f"Failed handling message from user {user.pk}")
              EventLog.objects.create(
                  event_type="error", user=user, message=f"Failed handling message: {text!r}"
              )
              send_sms(user, from_number, GENERIC_ERROR_MESSAGE)

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
              send_sms(None, to_numbers[0], text, tags=[RETRY_TAG])

        return Response(status=200)
