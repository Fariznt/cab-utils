from django.core.management.base import BaseCommand
from background_task import background
import requests
from seat_signal import utils
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from core.models import CourseSession, User
from seat_signal.models import SeatSignal
from django.conf import settings
from core.models import CourseSession
from core.models import User
import random
import time
import logging


logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Enables the background task that watches for course seat openings for the app Seat Signal'

    def handle(self, *args, **options):
        self.stdout.write("Successfully called course watching task")
        while True:
            try:
                logger.info("Checking for current SeatSignals")
                # loop over all sessions referenced by a seat signal
                sessions_w_signal = CourseSession.objects.filter(session_signals__isnull=False).distinct()
                logger.info(f'{sessions_w_signal.count()} CourseSessions found with associated SeatSignal')
                for session in sessions_w_signal: 
                    # Get seat availability            
                    payload = {
                        'key': 'crn:' + str(session.crn)
                    }
                    url = "https://cab.brown.edu/api/?page=fose&route=details"
                    headers = { # look like a browser to CAB's API
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    }
                    response = requests.post(url, json=payload, headers=headers)
                    course_details = response.json()
                    logger.info(f'Fetched details for CourseSession with crn:{session.crn}')
                    if course_details == None:
                        logger.info('Details json is None.')
                    else:
                        seats_string = course_details['seats'].partition('<span class="seats_avail">')[2].partition('</span>')[0]
                        if seats_string != "0":
                            logger.info(f'A nonzero seats_string {seats_string} detected.')

                            # Get users to notify
                            users = User.objects.filter(
                                id__in=session.session_signals.values_list('user_id', flat=True)
                            )
                            logger.info(f'Users watching this CourseSession: {users}')

                            # Notify them
                            for user in users:
                                # update database
                                SeatSignal.objects.filter(
                                    user=user, 
                                    session=session
                                ).delete()
                                # Contact user
                                self.send_signal(session.crn, user.phone_num)
                                logger.info(f'Notified {user}')
                                time.sleep(random.uniform(1, 3))
                                
                        # Randomized delay before next API call
                        time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.error(f"Error in SeatSignal task: {e}")
            finally:
                logger.info("End of check. Scheduling next SeatSignal check in 10 seconds...")
                time.sleep(10)

    def send_signal(self, crn, to_number) -> None:
        """Notifies the user (by call) of an open seat in the session they had SeatSignal watching"""
        # Create call voice message string
        session = CourseSession.objects.get(crn=crn)
        course_title = session.title
        section = session.section
        msg = (
            f"Seat Signal has detected an open seat for {course_title} "
            f"<break time='0.3s'/> section {section}."
            "<break time='1s'/> Proceed to registration."
        )
        # Create call voice message
        voice_resp = VoiceResponse()
        voice_resp.pause(length=1.5)
        voice_resp.say(msg, voice="alice")
        # Create client & call
        client = Client(settings.ACCOUNT_SID, settings.AUTH_TOKEN)
        call = client.calls.create(
            to=to_number, 
            from_= settings.FROM_NUMBER,
            twiml = voice_resp.to_xml()
        )

