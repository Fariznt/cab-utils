"""
The sms app's view layer: the Telnyx-facing pieces of the conversation.

Split by job: webhook.py the Telnyx endpoint, inbound_state_handler.py what we
do with a reply, and auth.py its signature check. (conversation.py, what we
say, and telnyx_client.py, the outbound call, live at the app root — neither
is a view.)

Re-exported here so callers (urls.py, tests) have one import path for the
app's public surface. Note that `mock.patch` must still target the defining
module - patching a name here rebinds only this namespace, not the module the
calling code resolves it from.
"""

from sms.conversation import (
    CAP_REACHED_MESSAGE,
    CONFIRM_RETRY_MESSAGE,
    EXIT_KEYWORDS,
    EXIT_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    HELP_CONFIRMATION_TEMPLATE,
    HELP_COURSE_MESSAGE,
    HELP_FOLLOWUP_DELAY_SECONDS,
    HELP_KEYWORD,
    HELP_MESSAGE,
    HELP_REMOVAL_MESSAGE,
    HELP_SECTION_MESSAGE,
    NO_WATCHES_MESSAGE,
    OPT_IN_MESSAGE,
    OPT_OUT_MESSAGE,
    REMOVAL_RETRY_MESSAGE,
    REMOVE_KEYWORD,
    REMOVE_PROMPT,
    SEAT_OPENED_MESSAGE,
    SIGNAL_SET_MESSAGE,
    START_KEYWORD,
    STOP_KEYWORDS,
    VIEW_KEYWORD,
    WATCH_REMOVED_MESSAGE,
    _confirm_prompt,
    _course_not_found_message,
    _course_prompt,
    _help_confirmation_message,
    _numbered_watches,
    _pending_course_label,
    _pending_session_label,
    _section_not_found_message,
    _section_prompt,
    _session_label,
    watch_list_message,
)
from sms.telnyx_client import send_sms
from sms.views.auth import SIGNATURE_TOLERANCE_SECONDS, TelnyxSignature
from sms.views.inbound_state_handler import _handle_state_message
from sms.views.webhook import (
    PERMANENT_ERROR_CODES,
    RETRY_DELAY_SECONDS,
    RETRY_TAG,
    TelnyxWebhook,
)
