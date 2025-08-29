from django.core.management.base import BaseCommand
from seat_signal.tasks import enable_seat_signal

class Command(BaseCommand):
    help = 'Enables the background task that watches for course seat openings for the app Seat Signal'

    def handle(self, *args, **options):
        enable_seat_signal() # start watching for course seat availabiity (SeatSignal app)
        self.stdout.write("Successfully called course watching task")
