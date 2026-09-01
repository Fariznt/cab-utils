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

from core.models import CourseSession
from seat_signal.services import course_is_uncapped, create_watch, get_watches_for_user, remove_watch
from seat_signal.utils import get_current_sem_id
from sms.conversation import (
    CAP_REACHED_MESSAGE,
    CONFIRM_RETRY_MESSAGE,
    EXIT_KEYWORDS,
    EXIT_MESSAGE,
    HELP_COURSE_MESSAGE,
    HELP_KEYWORD,
    HELP_REMOVAL_MESSAGE,
    HELP_SECTION_MESSAGE,
    NO_WATCHES_MESSAGE,
    REMOVAL_RETRY_MESSAGE,
    REMOVE_KEYWORD,
    REMOVE_PROMPT,
    SIGNAL_SET_MESSAGE,
    VIEW_KEYWORD,
    WATCH_REMOVED_MESSAGE,
    _confirm_prompt,
    _course_not_found_message,
    _course_prompt,
    _course_uncapped_message,
    _help_confirmation_message,
    _numbered_watches,
    _section_not_found_message,
    _section_prompt,
    _session_label,
    watch_list_message,
)
from sms.models import ConversationState
from sms.telnyx_client import send_sms
from sms.views.match_utils import match_course, match_section

logger = logging.getLogger(__name__)


def _handle_awaiting_course(user, conversation_state, keyword, text):
    """The default state: a course name, or one of the VIEW/REMOVE commands."""
    if keyword == VIEW_KEYWORD:
        watches = list(get_watches_for_user(user))
        if watches:
            send_sms(user, user.phone_num, watch_list_message(watches))
        else:
            send_sms(user, user.phone_num, NO_WATCHES_MESSAGE)
    elif keyword == REMOVE_KEYWORD:
        watches = list(get_watches_for_user(user))
        if watches:
            conversation_state.state = ConversationState.AWAITING_REMOVAL
            conversation_state.save()
            send_sms(user, user.phone_num, f"{_numbered_watches(watches)}\n{REMOVE_PROMPT}")
        else:
            # nothing to remove, so stay put rather than stranding them in the removal flow
            send_sms(user, user.phone_num, NO_WATCHES_MESSAGE)
    # cap check sits below VIEW/REMOVE so a capped user can still get out of it
    elif get_watches_for_user(user).count() >= settings.SIGNAL_CAP:
        send_sms(user, user.phone_num, CAP_REACHED_MESSAGE)
    else:
        # pinned here rather than at confirmation so the semester can't shift mid-conversation
        sem_id = get_current_sem_id()
        code = match_course(text, sem_id)
        if code is None:
            send_sms(user, user.phone_num, _course_not_found_message())
            return
        # checked live against C@B rather than inferred, since which sections
        # work this way isn't stable enough to hardcode (see course_is_uncapped)
        if course_is_uncapped(code, sem_id):
            send_sms(user, user.phone_num, _course_uncapped_message())
            return
        # only the best match is taken; confirmation is what catches a wrong guess
        conversation_state.pending_code = code
        conversation_state.pending_sem_id = sem_id
        conversation_state.state = ConversationState.AWAITING_SECTION
        conversation_state.save()
        send_sms(user, user.phone_num, _section_prompt(conversation_state))


def _handle_awaiting_section(user, conversation_state, keyword, text):
    """The user just picked a course and owes us a section code."""
    section = match_section(
        text, conversation_state.pending_code, conversation_state.pending_sem_id
    )
    if section is None:
        send_sms(user, user.phone_num, _section_not_found_message(conversation_state))
        return

    conversation_state.pending_section = section
    conversation_state.state = ConversationState.AWAITING_CONFIRMATION
    conversation_state.save()
    send_sms(user, user.phone_num, _confirm_prompt(conversation_state))


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
        send_sms(user, user.phone_num, confirmation)
    else:
        send_sms(user, user.phone_num, CONFIRM_RETRY_MESSAGE)


def _handle_awaiting_removal(user, conversation_state, keyword, text):
    """A numbered watch list went out; the reply picks one to delete."""
    # re-read the list rather than trusting the numbering we sent: a seat
    # signal can disappear between the prompt and the reply if the poll
    # loop fires for it
    watches = list(get_watches_for_user(user))
    choice = int(keyword) if keyword.isdigit() else 0
    if 1 <= choice <= len(watches):
        session = watches[choice - 1].session
        remove_watch(user, session)
        conversation_state.state = ConversationState.AWAITING_COURSE
        conversation_state.save()
        send_sms(
            user,
            user.phone_num,
            f"{WATCH_REMOVED_MESSAGE.format(session=_session_label(session))} {_course_prompt()}",
        )
    else:
        send_sms(user, user.phone_num, REMOVAL_RETRY_MESSAGE)


# HELP and EXIT mean the same thing in every state, so they're answered once in
# _handle_state_message; only the help wording differs per state.
# Callables rather than plain strings so a state's help can name what the user
# is actually being asked about; the static ones just ignore the argument.
STATE_HELP = {
    ConversationState.AWAITING_COURSE: lambda conversation_state: HELP_COURSE_MESSAGE,
    ConversationState.AWAITING_SECTION: lambda conversation_state: HELP_SECTION_MESSAGE,
    ConversationState.AWAITING_CONFIRMATION: _help_confirmation_message,
    ConversationState.AWAITING_REMOVAL: lambda conversation_state: HELP_REMOVAL_MESSAGE,
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
    send_sms(user, user.phone_num, f"{EXIT_MESSAGE} {_course_prompt()}")


def _handle_state_message(user, text):
    """
    Handles the inbound SMS message and updates the conversation state accordingly. 
    Opt-in/opt-out logic is handled by parent function in sms/views/webhook.py

    Args:
        user: The User object representing the user sending the SMS.
        text: The text of the SMS message.

    Returns:
        None.
    """
    conversation_state = user.conversation_state
    text = (text or "").strip()
    keyword = text.upper()

    if not text:
        # no real text to act on (e.g. an MMS with no text body) - say nothing
        # and let the user send something we can actually parse
        return

    # the generic help message already went out from post(); what's left is the
    # tailored follow-up for wherever the user is in the flow
    if keyword == HELP_KEYWORD:
        send_sms(user, user.phone_num, STATE_HELP[conversation_state.state](conversation_state))
        return

    if keyword in EXIT_KEYWORDS:
        _exit_to_course(user, conversation_state)
        return

    STATE_HANDLERS[conversation_state.state](user, conversation_state, keyword, text)
