"""
The sms app's view layer and the pieces the conversation is built from.

Split by job: conversation.py holds what we say, flow.py what we do with a
reply, webhook.py the Telnyx endpoint, auth.py its signature check, and
telnyx_client.py the outbound call.

Re-exported here so callers (urls.py, tests) have one import path for the
app's public surface. Note that `mock.patch` must still target the defining
module - patching a name here rebinds only this namespace, not the module the
calling code resolves it from.
"""

from sms.views.auth import SIGNATURE_TOLERANCE_SECONDS, TelnyxSignature
from sms.views.conversation import (
    CAP_REACHED_MESSAGE,
    CONFIRM_PROMPT,
    CONFIRM_RETRY_MESSAGE,
    EXIT_KEYWORDS,
    EXIT_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    HELP_CONFIRMATION_MESSAGE,
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
    SECTION_PROMPT,
    SIGNAL_SET_MESSAGE,
    START_KEYWORD,
    STOP_KEYWORDS,
    VIEW_KEYWORD,
    WATCH_LIST_HEADER,
    WATCH_REMOVED_MESSAGE,
    _course_not_found_message,
    _course_prompt,
    _numbered_watches,
    _section_not_found_message,
    _session_label,
)
from sms.views.flow import _handle_state_message, _send
from sms.views.telnyx_client import send_sms
from sms.views.webhook import (
    PERMANENT_ERROR_CODES,
    RETRY_DELAY_SECONDS,
    RETRY_TAG,
    TelnyxWebhook,
)
