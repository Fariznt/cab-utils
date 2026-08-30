"""
What the SMS conversation does: the per-state handlers and the dispatch that
picks between them.

Each conversation state gets one handler, all sharing a signature so the
dispatch table below can call them uniformly. HELP and EXIT are handled once in
_handle_state_message rather than in every handler, since they mean the same
thing everywhere, so a handler only ever contains its own state's logic.

Adding a state: write a handler, then add it to STATE_HELP and STATE_HANDLERS.
"""

import logging

from django.conf import settings
from django.utils import timezone

from core.models import CourseSession, EventLog
from seat_signal.services import create_watch, get_watches_for_user, remove_watch
from seat_signal.utils import get_current_sem_id
from sms.models import ConversationState, MessageHistory
from sms.views.conversation import (
    CAP_REACHED_MESSAGE,
    CONFIRM_PROMPT,
    CONFIRM_RETRY_MESSAGE,
    EXIT_KEYWORDS,
    EXIT_MESSAGE,
    HELP_CONFIRMATION_MESSAGE,
    HELP_COURSE_MESSAGE,
    HELP_KEYWORD,
    HELP_REMOVAL_MESSAGE,
    HELP_SECTION_MESSAGE,
    NO_WATCHES_MESSAGE,
    REMOVAL_RETRY_MESSAGE,
    REMOVE_KEYWORD,
    REMOVE_PROMPT,
    SECTION_PROMPT,
    SIGNAL_SET_MESSAGE,
    VIEW_KEYWORD,
    WATCH_LIST_HEADER,
    WATCH_REMOVED_MESSAGE,
    _course_not_found_message,
    _course_prompt,
    _numbered_watches,
    _section_not_found_message,
    _session_label,
)
from sms.views.telnyx_client import send_sms

logger = logging.getLogger(__name__)


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


def _active_watches(user):
    """
    The user's watches in a stable order. Ordering is load-bearing, not cosmetic:
    the numbers in the REMOVE list have to mean the same thing when the user
    replies as they did when we sent the list, and an unordered queryset gives
    Postgres license to hand back a different order each time.
    """
    return get_watches_for_user(user).order_by("datetime_created")


def _register_course(conversation_state, text): # TODO: implementation is tentative
    """
    Saves the user's course selection and moves them on to picking a section.
    Takes the text verbatim for now - trigram matching goes here later, and
    raises ValueError once there's a match step that can fail.
    """
    conversation_state.pending_code = text
    # pinned here rather than at confirmation so the semester can't shift mid-conversation
    conversation_state.pending_sem_id = get_current_sem_id()
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


def _handle_awaiting_course(user, conversation_state, keyword, text):
    """The default state: a course name, or one of the VIEW/REMOVE commands."""
    if keyword == VIEW_KEYWORD:
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


def _handle_awaiting_section(user, conversation_state, keyword, text):
    """The user just picked a course and owes us a section code."""
    try:
        _register_section(conversation_state, text)
    except ValueError:
        _send(user, user.phone_num, f"{_section_not_found_message()} {SECTION_PROMPT}")


def _handle_awaiting_confirmation(user, conversation_state, keyword, text):
    """The selection is shown and we're waiting on a YES to commit it."""
    if keyword == "YES":
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


def _handle_awaiting_removal(user, conversation_state, keyword, text):
    """A numbered watch list went out; the reply picks one to delete."""
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


# HELP and EXIT mean the same thing in every state, so they're answered once in
# _handle_state_message; only the help wording differs per state.
STATE_HELP = {
    ConversationState.AWAITING_COURSE: HELP_COURSE_MESSAGE,
    ConversationState.AWAITING_SECTION: HELP_SECTION_MESSAGE,
    ConversationState.AWAITING_CONFIRMATION: HELP_CONFIRMATION_MESSAGE,
    ConversationState.AWAITING_REMOVAL: HELP_REMOVAL_MESSAGE,
}

STATE_HANDLERS = {
    ConversationState.AWAITING_COURSE: _handle_awaiting_course,
    ConversationState.AWAITING_SECTION: _handle_awaiting_section,
    ConversationState.AWAITING_CONFIRMATION: _handle_awaiting_confirmation,
    ConversationState.AWAITING_REMOVAL: _handle_awaiting_removal,
}


def _exit_to_course(user, conversation_state):
    """Drops whatever was in progress and returns the user to the default state."""
    conversation_state.state = ConversationState.AWAITING_COURSE
    conversation_state.save()
    _send(user, user.phone_num, f"{EXIT_MESSAGE} {_course_prompt()}")


def _handle_state_message(user, text):
    conversation_state = user.conversation_state
    keyword = (text or "").strip().upper()

    if not keyword:
        # no real text to act on (e.g. an MMS with no text body) - say nothing
        # and let the user send something we can actually parse
        return

    # the generic help message already went out from post(); what's left is the
    # tailored follow-up for wherever the user is in the flow
    if keyword == HELP_KEYWORD:
        _send(user, user.phone_num, STATE_HELP[conversation_state.state])
        return

    if keyword in EXIT_KEYWORDS:
        _exit_to_course(user, conversation_state)
        return

    STATE_HANDLERS[conversation_state.state](user, conversation_state, keyword, text)
