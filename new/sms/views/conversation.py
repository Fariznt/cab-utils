"""
What the SMS conversation says: every user-facing string, plus the small
functions that build the ones depending on runtime state (the current semester,
a user's watch list).

Nothing here writes to the database or decides what happens next - that is
flow.py's job. Keeping the copy in one file means reworking wording never means
opening the webhook or the flow logic.
"""

from core.models import CourseSession
from seat_signal.utils import get_current_sem_id, get_sem_str

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
HELP_CONFIRMATION_TEMPLATE = (
    "Reply YES to set a seat signal for {selection}, or EXIT to leave the course picking flow."
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
        f"Which {get_sem_str(get_current_sem_id())} course would you like to watch for seats? "
        "Reply VIEW to see your active seat signals, or REMOVE to delete one."
    )
def _section_prompt(conversation_state):
    return (
        f"Which section of {_pending_course_label(conversation_state)}? "
        "Reply with a section code like 'S01'."
    )


def _confirm_prompt(conversation_state):
    return f"Is this correct? {_pending_session_label(conversation_state)}"


def _help_confirmation_message(conversation_state):
    return HELP_CONFIRMATION_TEMPLATE.format(
        selection=_pending_session_label(conversation_state)
    )


def _course_not_found_message():
    return f"Could not find that course in {get_sem_str(get_current_sem_id())}."


def _section_not_found_message(conversation_state):
    return f"Could not find that section for {_pending_course_label(conversation_state)}."

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


def _pending_course_label(conversation_state):
    """The course being picked, named the way a student would recognise it."""
    title = (
        CourseSession.objects.filter(
            code=conversation_state.pending_code, sem_id=conversation_state.pending_sem_id
        )
        .values_list("title", flat=True)
        .first()
    )
    return f"{conversation_state.pending_code} ({title})" if title else conversation_state.pending_code


def _pending_session_label(conversation_state):
    """The full course + section selection, before it becomes a SeatSignal."""
    return (
        f"{conversation_state.pending_code} {conversation_state.pending_section} "
        f"({get_sem_str(conversation_state.pending_sem_id)})"
    )


def _session_label(session):
    """Human-readable course session, e.g. 'CSCI 0320 S01 (Fall 2026)'."""
    return f"{session.code} {session.section} ({get_sem_str(session.sem_id)})"


def _numbered_watches(watches):
    """Numbered list. These numbers are what the user replies with to remove one."""
    return "\n".join(
        f"{i}. {_session_label(watch.session)}" for i, watch in enumerate(watches, start=1)
    )
