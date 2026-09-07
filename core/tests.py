import logging
import uuid

from django.db import transaction
from django.test import TestCase

from core.fields import EncryptedPhoneField
from core.models import EventLog, User


class EncryptedPhoneFieldTests(TestCase):
    """
    Pins down the reason AES-SIV was chosen over Fernet: same plaintext must
    always produce the same ciphertext, so a DB-level unique/exact lookup on
    phone_num works.
    """

    def test_round_trip_through_db(self):
        user = User.objects.create_user(phone_num="+15551234567")
        reloaded = User.objects.get(pk=user.pk)
        self.assertEqual(reloaded.phone_num, "+15551234567")

    def test_encryption_is_deterministic(self):
        field = EncryptedPhoneField()
        first = field.get_prep_value("+15551234567")
        second = field.get_prep_value("+15551234567")
        self.assertEqual(first, second)

    def test_lookup_by_phone_number(self):
        User.objects.create_user(phone_num="+15551234567")
        self.assertTrue(User.objects.filter(phone_num="+15551234567").exists())
        self.assertFalse(User.objects.filter(phone_num="+19998887777").exists())


class EventLogBridgeTests(TestCase):
    """
    core/signals.py is what puts EventLog rows in front of the handlers in
    settings.py, so it has to fire at the row's own level, carry enough context
    to identify the row, and stay silent for a rolled-back one.
    """

    def test_row_is_logged_at_its_own_level(self):
        with self.assertLogs("cab_utils.events", level="DEBUG") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                EventLog.objects.create(event_type="error", level="ERROR", message="boom")
        self.assertEqual(logs.records[0].levelname, "ERROR")
        self.assertIn("boom", logs.output[0])

    def test_message_carries_user_context(self):
        # account_created writes no message, so the user id is all that
        # identifies it once it reaches the log.
        user = User.objects.create_user(phone_num="+15551234567")
        with self.assertLogs("cab_utils.events", level="DEBUG") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                EventLog.objects.create(event_type="account_created", user=user)
        self.assertIn(f"user={user.pk}", logs.output[0])

    def test_rolled_back_row_is_not_logged(self):
        with self.assertNoLogs("cab_utils.events", level="DEBUG"):
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    EventLog.objects.create(event_type="error", level="ERROR", message="never happened")
                    transaction.set_rollback(True)


def _root_handler(name):
    return next(h for h in logging.getLogger().handlers if h.name == name)


class LoggingConfigTests(TestCase):
    """
    Pins down settings.py's LOGGING dict itself: one unfiltered file handler
    that everything reaches, whatever its level. This is the routing every
    EventLog write (via the bridge above) and every plain logger.error/exception
    call in the codebase relies on. There is deliberately no level-gated second
    handler to assert on - separating the serious records out happens at the log
    destination (a CloudWatch metric filter), not here.
    """

    def test_file_accepts_everything(self):
        self.assertEqual(_root_handler("file").level, logging.NOTSET)

    def test_records_reach_app_log_at_every_level(self):
        marker = uuid.uuid4().hex
        logger = logging.getLogger("cab_utils.events")
        logger.info("info %s", marker)
        logger.error("error %s", marker)
        for handler in logging.getLogger().handlers:
            handler.flush()

        with open(_root_handler("file").baseFilename) as f:
            app_log = f.read()
        self.assertIn(f"info {marker}", app_log)
        self.assertIn(f"error {marker}", app_log)
