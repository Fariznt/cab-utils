import logging
import random
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from seat_signal import services
from seat_signal.models import Heartbeat, SeatSignal
from seat_signal.signals import seat_opened

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Polls C@B for open seats on every actively-watched CourseSession. Runs forever (systemd restarts it on crash)."

    def handle(self, *args, **options):
        self.stdout.write("Starting seat signal poll loop")
        while True:
            # find_signals_with_open_seats isolates one bad course's failure from
            # the rest of the pass (see seat_signal/services.py).
            for session, users in services.find_signals_with_open_seats():
                logger.info(f"Open seat found for {session}, notifying {len(users)} user(s)")
                # One-shot notification: clear the watch once the user's been told.
                SeatSignal.objects.filter(session=session).delete()
                for user in users:
                    seat_opened.send(sender=self.__class__, user=user, session=session)
                    # Randomized delay between notifications / throttling
                    time.sleep(random.uniform(1, 3))
                time.sleep(random.uniform(2, 4))

            if services.last_pass_failures == 0:
                Heartbeat.objects.update_or_create(
                    name=Heartbeat.POLL_SEATS, defaults={"last_seen": timezone.now()}
                )
            time.sleep(10)
