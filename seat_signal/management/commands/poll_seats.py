import logging
import random
import time

from django.core.management.base import BaseCommand

from seat_signal.models import SeatSignal
from seat_signal.services import find_signals_with_open_seats
from seat_signal.signals import seat_opened

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Polls C@B for open seats on every actively-watched CourseSession. Runs forever (systemd restarts it on crash)."

    def handle(self, *args, **options):
        self.stdout.write("Starting seat signal poll loop")
        while True:
            checked = 0
            # find_signals_with_open_seats isolates one bad course's failure from
            # the rest of the pass (see seat_signal/services.py).
            for session, users in find_signals_with_open_seats():
                checked += 1
                logger.info(f"Open seat found for {session}, notifying {len(users)} user(s)")
                # One-shot notification: clear the watch once the user's been told.
                SeatSignal.objects.filter(session=session).delete()
                for user in users:
                    seat_opened.send(sender=self.__class__, user=user, session=session)
                    # Randomized delay between notifications / throttling
                    time.sleep(random.uniform(1, 3))
                time.sleep(random.uniform(2, 4))

            # Heartbeat: distinguishes "running normally" from "died silently".
            # A log line instead of EventLog row.. polling pollutes the log. 
            # Cloudwatch integration should still be done---alarm on absence of heartbeat
            logger.info(f"Poll cycle complete, {checked} open seat(s) found")
            time.sleep(10)
