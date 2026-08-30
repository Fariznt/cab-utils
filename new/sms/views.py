import base64
import logging
import time
import datetime
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import CourseSession, EventLog, User
from seat_signal.services import create_watch, get_watches_for_user, remove_watch
from seat_signal.utils import get_sem_str
from sms.models import ConversationState, MessageHistory, OptInStatus
from sms.telnyx_client import send_sms

logger = logging.getLogger(__name__)

# FLOW DEFINITIONS ==============================================================

START_KEYWORD = "START"
HELP_KEYWORD = "HELP"
VIEW_KEYWORD = "VIEW"
REMOVE_KEYWORD = "REMOVE"
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

HELP_FOLLOWUP_DELAY_SECONDS = 1

# Sent instead of the normal per-state prompt when the user asked for HELP.
# Wording is a placeholder - not finalized.
HELP_COURSE_MESSAGE = (
    "You're picking a course to watch. Reply with the course name or code, like "
    "'CSCI 0320'. Reply VIEW to see your active seat signals, or REMOVE to delete one."
)
HELP_SECTION_MESSAGE = (
    "Reply with the section code for that course, like 'S01'. Reply EXIT to leave the "
    "course picking flow."
)
HELP_CONFIRMATION_MESSAGE = (
    "Reply YES to confirm that seat signal, or EXIT to leave the course picking flow."
)
HELP_REMOVAL_MESSAGE = (
    "Reply with the number of the seat signal you want to remove, or EXIT to leave "
    "without removing anything."
)

EXIT_MESSAGE = "Exited the course picking flow."
EXIT_KEYWORDS = {"EXIT", "NO"}

CONFIRM_RETRY_MESSAGE = (
    "Sorry, I don't understand. Reply YES to confirm, or EXIT to leave the course picking flow."
)

# Seat signal viewing and removal, both reachable from the default AWAITING_COURSE state.
WATCH_LIST_HEADER = "Your active seat signals:"
NO_WATCHES_MESSAGE = "You don't have any active seat signals."
REMOVE_PROMPT = "Which one would you like to remove? Reply with its number, or EXIT to cancel."
REMOVAL_RETRY_MESSAGE = (
    "Sorry, I don't understand. Reply with the number of the seat signal to remove, "
    "or EXIT to cancel."
)
WATCH_REMOVED_MESSAGE = "Seat signal for {session} has been removed."

# The plain per-state prompts, re-sent after a failed selection. Wording is a
# placeholder - not finalized. The ones naming a semester are functions because
# the semester is resolved at send time, not at import time.
def _course_prompt():
    return (
        f"Which {get_sem_str(_get_current_sem_id())} course would you like to watch for seats? "
        "Reply VIEW to see your active seat signals, or REMOVE to delete one."
    )
SECTION_PROMPT = "Which section of that course? Reply with a section code like 'S01'."
CONFIRM_PROMPT = "Is the following course and section selection correct?"



def _course_not_found_message():
    return f"Could not find that course in {get_sem_str(_get_current_sem_id())}."


def _section_not_found_message():
    return f"Could not find that section in {get_sem_str(_get_current_sem_id())}."

SIGNAL_SET_MESSAGE = (
  "Seat signal for {session} has been set. To view course sessions being watched, reply VIEW."
  "To remove a course session, reply REMOVE."
)
CAP_REACHED_MESSAGE = (
    "That's the most seat signals you can have at once, so remove one before adding another."
)
GENERIC_ERROR_MESSAGE = (
    "Something went wrong. Please report this error through the contact info at "
    "https://bit.ly/4ik1eEZ."
)

# ACADEMIC CALENDAR CONSTANTS =====================================================================

CALENDAR_TIMEZONE = ZoneInfo("America/New_York")

# Undergraduate course-registration windows for the 2026-2027 academic year, as
# (start, end, sem_id), taken from Brown's registrar calendar. Must stay sorted
# by start and non-overlapping - _get_current_sem_id relies on both. The
# in-semester windows run through the last day to add a course, since that's
# when watching for an open seat stops being useful.
# This constant needs an update every academic year as registration period dates are released
REGISTRATION_PERIODS = (
    (datetime.date(2026, 3, 30), datetime.date(2026, 4, 9), "202600"),    # Summer 2026
    (datetime.date(2026, 4, 14), datetime.date(2026, 4, 21), "202610"),   # Fall 2026 pre-registration
    (datetime.date(2026, 4, 22), datetime.date(2026, 6, 17), "202600"),   # Summer 2026 re-opens, through last day to change courses (no distinct add-with-fee deadline for Summer)
    (datetime.date(2026, 9, 4), datetime.date(2026, 10, 6), "202610"),    # Fall 2026 through add deadline
    (datetime.date(2026, 11, 10), datetime.date(2026, 11, 17), "202620"), # Spring 2027 pre-registration
    (datetime.date(2026, 11, 18), datetime.date(2026, 12, 16), "202615"), # Winter 2027 (Wintersession)
    (datetime.date(2027, 1, 22), datetime.date(2027, 2, 24), "202620"),   # Spring 2027 through add deadline
    (datetime.date(2027, 4, 19), datetime.date(2027, 4, 27), "202710"),   # Fall 2027 pre-registration
)

# TELNYX MESSAGING DEFINITIONS =====================================================================

# How far out of date a signed webhook may be before it's treated as a replay.
SIGNATURE_TOLERANCE_SECONDS = 300

# message.finalized error codes that will not succeed on retry.
PERMANENT_ERROR_CODES = {"40001", "47000"}
RETRY_TAG = "retry"
RETRY_DELAY_SECONDS = 2


def _send(user, to_number, text, tags=None):
    """Sends a text, then records it to the event log and the user's transcript."""
    send_sms(to_number, text, tags=tags)
    EventLog.objects.create(event_type="sms_sent", user=user, message=text)

    # Telnyx stamps inbound messages for us; outbound ones we stamp ourselves.
    history, _ = MessageHistory.objects.get_or_create(user=user)
    history.messages.append(
        {"direction": "outbound", "body": text, "at": timezone.now().isoformat()}
    )
    history.save()


# SEAT SIGNAL VIEWING AND REMOVAL FUNCTIONS =====================================================================

def _active_watches(user):
    """
    The user's watches in a stable order. Ordering is load-bearing, not cosmetic:
    the numbers in the REMOVE list have to mean the same thing when the user
    replies as they did when we sent the list, and an unordered queryset gives
    Postgres license to hand back a different order each time.
    """
    return get_watches_for_user(user).order_by("datetime_created")


def _session_label(session):
    """Human-readable course session, e.g. 'CSCI 0320 S01 (Fall 2026)'."""
    return f"{session.code} {session.section} ({get_sem_str(session.sem_id)})"


def _numbered_watches(watches):
    """Numbered list. These numbers are what the user replies with to remove one."""
    return "\n".join(
        f"{i}. {_session_label(watch.session)}" for i, watch in enumerate(watches, start=1)
    )


class TelnyxSignature(BasePermission):
    """
    Verifies Telnyx's Ed25519 webhook signature. The caller is Telnyx, not a
    Django user, so this is the only authentication this endpoint has - without
    it, anyone who found the URL could POST a message.received claiming to be
    any phone number and drive that user's conversation.
    """

    message = "Invalid Telnyx signature."

    def has_permission(self, request, view):
        signature = request.headers.get("telnyx-signature-ed25519", "")
        timestamp = request.headers.get("telnyx-timestamp", "")
        try:
            # An old-but-validly-signed payload is a replay, so the timestamp is
            # checked as well as signed. Telnyx signs "<timestamp>|<raw body>".
            if abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
                logger.warning("Rejected webhook with a stale Telnyx timestamp")
                return False
            public_key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(settings.TELNYX_PUBLIC_KEY)
            )
            public_key.verify(
                base64.b64decode(signature), f"{timestamp}|".encode() + request.body
            )
        except (InvalidSignature, ValueError, TypeError):
            logger.warning("Rejected webhook with an invalid Telnyx signature")
            return False
        return True


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
            _send(user, from_number, HELP_MESSAGE)
            time.sleep(HELP_FOLLOWUP_DELAY_SECONDS)

          # opt-in/opt-out gating sits above messaging state. STOP is handled the
          # same for a brand-new number as for a known one: a cold number whose
          # first word is STOP is opting out, not signing up, and answering that
          # with the marketing greeting would be a violation.
          if keyword in STOP_KEYWORDS:
            opt_in_status.is_opted_in = False
            opt_in_status.save()
            _send(user, from_number, OPT_OUT_MESSAGE)
          elif created:
            # first contact is a greeting only - their message isn't a course yet
            _send(user, from_number, OPT_IN_MESSAGE)
          elif not opt_in_status.is_opted_in:
            if keyword == START_KEYWORD:
              opt_in_status.is_opted_in = True
              opt_in_status.save()
              user.conversation_state.state = ConversationState.AWAITING_COURSE
              user.conversation_state.save()
              _send(user, from_number, OPT_IN_MESSAGE)
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
              _send(user, from_number, GENERIC_ERROR_MESSAGE)

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


def _get_current_sem_id():
    """
    Returns the semester the picking flow scopes to - never asked for, always
    automatic. It's the semester of the registration period we're currently in,
    or if we're between periods, of the next one to open.
    """
    # Brown's calendar is Eastern; settings.TIME_ZONE is UTC, so a plain
    # localdate() would roll over to tomorrow after 8pm ET.
    today = timezone.now().astimezone(CALENDAR_TIMEZONE).date()

    # Periods are sorted and non-overlapping, so the first one that hasn't ended
    # is either the one we're in or the next one to open - both are the semester
    # we want, so no separate lookahead pass is needed.
    for _, end, sem_id in REGISTRATION_PERIODS:
        if today <= end:
            return sem_id

    # Ran off the end of the table - the calendar needs the next academic year added.
    logger.error(f"No registration period covers {today}, REGISTRATION_PERIODS needs updating")
    return REGISTRATION_PERIODS[-1][2]


def _register_course(conversation_state, text): # TODO: implementation is tentative
    """
    Saves the user's course selection and moves them on to picking a section.
    Takes the text verbatim for now - trigram matching goes here later, and
    raises ValueError once there's a match step that can fail.
    """
    conversation_state.pending_code = text
    # pinned here rather than at confirmation so the semester can't shift mid-conversation
    conversation_state.pending_sem_id = _get_current_sem_id()
    conversation_state.state = ConversationState.AWAITING_SECTION
    conversation_state.save()

    user = conversation_state.user
    _send(user, user.phone_num, SECTION_PROMPT)


def _register_section(conversation_state, text): # TODO: implementation is tentative
    """
    Saves the user's section selection and moves them on to confirming.
    Takes the text verbatim for now - regex matching goes here later, and
    raises ValueError once there's a match step that can fail.
    """
    conversation_state.pending_section = text
    conversation_state.state = ConversationState.AWAITING_CONFIRMATION
    conversation_state.save()

    user = conversation_state.user
    selection = f"{conversation_state.pending_code} {conversation_state.pending_section}"
    _send(user, user.phone_num, f"{CONFIRM_PROMPT} {selection}")


def _handle_state_message(user, text):
    conversation_state = user.conversation_state
    keyword = (text or "").strip().upper()

    if not keyword:
        # no real text to act on (e.g. an MMS with no text body) - say nothing
        # and let the user send something we can actually parse
        return

    # the generic help message already went out from post(); what's left is the
    # tailored follow-up for wherever the user is in the flow
    needs_help = keyword == HELP_KEYWORD

    # HANDLE MESSAGE WHEN AWAITING COURSE
    if conversation_state.state == ConversationState.AWAITING_COURSE:
        if needs_help:
            _send(user, user.phone_num, HELP_COURSE_MESSAGE)
        elif keyword in EXIT_KEYWORDS:
            conversation_state.state = ConversationState.AWAITING_COURSE
            conversation_state.save()
            _send(user, user.phone_num, f"{EXIT_MESSAGE} {_course_prompt()}")
        elif keyword == VIEW_KEYWORD:
            watches = list(_active_watches(user))
            if watches:
                _send(user, user.phone_num, f"{WATCH_LIST_HEADER}\n{_numbered_watches(watches)}")
            else:
                _send(user, user.phone_num, NO_WATCHES_MESSAGE)
        elif keyword == REMOVE_KEYWORD:
            watches = list(_active_watches(user))
            if watches:
                conversation_state.state = ConversationState.AWAITING_REMOVAL
                conversation_state.save()
                _send(user, user.phone_num, f"{_numbered_watches(watches)}\n{REMOVE_PROMPT}")
            else:
                # nothing to remove, so stay put rather than stranding them in the removal flow
                _send(user, user.phone_num, NO_WATCHES_MESSAGE)
        # cap check sits below VIEW/REMOVE so a capped user can still get out of it
        elif get_watches_for_user(user).count() >= settings.SIGNAL_CAP:
            _send(user, user.phone_num, CAP_REACHED_MESSAGE)
        else:
            try:
                _register_course(conversation_state, text)
            except ValueError:
                _send(user, user.phone_num, f"{_course_not_found_message()} {_course_prompt()}")

  # HANDLE MESSAGE WHEN AWAITING SECTION
    elif conversation_state.state == ConversationState.AWAITING_SECTION: 
        if needs_help:
            _send(user, user.phone_num, HELP_SECTION_MESSAGE)
        elif keyword in EXIT_KEYWORDS:
            conversation_state.state = ConversationState.AWAITING_COURSE
            conversation_state.save()
            _send(user, user.phone_num, f"{EXIT_MESSAGE} {_course_prompt()}")
        else:
            try:
                _register_section(conversation_state, text)
            except ValueError:
                _send(user, user.phone_num, f"{_section_not_found_message()} {SECTION_PROMPT}")

    # HANDLE MESSAGE WHEN AWAITING CONFIRMATION
    elif conversation_state.state == ConversationState.AWAITING_CONFIRMATION: 
        if needs_help:
            _send(user, user.phone_num, HELP_CONFIRMATION_MESSAGE)
        elif keyword in EXIT_KEYWORDS:
            conversation_state.state = ConversationState.AWAITING_COURSE
            conversation_state.save()
            _send(user, user.phone_num, f"{EXIT_MESSAGE} {_course_prompt()}")
        elif keyword == "YES":
            session = CourseSession.objects.get(
                code=conversation_state.pending_code,
                section=conversation_state.pending_section,
                sem_id=conversation_state.pending_sem_id,
            )
            create_watch(user, session)
            conversation_state.state = ConversationState.AWAITING_COURSE
            conversation_state.save()

            confirmation = SIGNAL_SET_MESSAGE.format(session=_session_label(session))
            # tack the cap notice on only once this watch fills the last slot
            if get_watches_for_user(user).count() >= settings.SIGNAL_CAP:
                confirmation += f" {CAP_REACHED_MESSAGE}"
            _send(user, user.phone_num, confirmation)
        else:
            _send(user, user.phone_num, CONFIRM_RETRY_MESSAGE)

    # HANDLE MESSAGE WHEN AWAITING REMOVAL
    elif conversation_state.state == ConversationState.AWAITING_REMOVAL:
        if needs_help:
            _send(user, user.phone_num, HELP_REMOVAL_MESSAGE)
        elif keyword in EXIT_KEYWORDS:
            conversation_state.state = ConversationState.AWAITING_COURSE
            conversation_state.save()
            _send(user, user.phone_num, f"{EXIT_MESSAGE} {_course_prompt()}")
        else:
            # re-read the list rather than trusting the numbering we sent: a seat
            # signal can disappear between the prompt and the reply if the poll
            # loop fires for it
            watches = list(_active_watches(user))
            choice = int(keyword) if keyword.isdigit() else 0
            if 1 <= choice <= len(watches):
                session = watches[choice - 1].session
                remove_watch(user, session)
                conversation_state.state = ConversationState.AWAITING_COURSE
                conversation_state.save()
                _send(
                    user,
                    user.phone_num,
                    WATCH_REMOVED_MESSAGE.format(session=_session_label(session)),
                )
            else:
                _send(user, user.phone_num, REMOVAL_RETRY_MESSAGE)
