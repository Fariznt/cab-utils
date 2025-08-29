from background_task import background
from background_task.models import Task
import requests
import json
from seat_signal import utils
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from core.models import CourseSession, User
from seat_signal.models import SeatSignal
from django.conf import settings
from core.models import CourseSession
from core.models import User

@background(schedule=0) # begin immediately, repeat every 10 seconds
def enable_seat_signal(repeat=10, repeat_until=None):
    """
    Background task that asynchronously polls C@B API for seat availability based on current SeatSignals in database
    """
    print("func called, prints working")
    # loop over all sessions referenced by a seat signal
    sessions_w_signal = CourseSession.objects.filter(session_signals__isnull=False).distinct()
    print(str(sessions_w_signal))
    for session in sessions_w_signal: 
        print("looped")
        # Get seat availability            
        payload = {
            'key': 'crn:' + str(session.crn)
        }
        url = "https://cab.brown.edu/api/?page=fose&route=details"
        response = requests.post(url, json=payload)
        course_details = response.json()
        seats_string = course_details['seats'].partition('<span class="seats_avail">')[2].partition('</span>')[0]

        if seats_string != "0":
            print("noticed seat availability")
            # Get users to notify
            users = User.objects.filter(
                id__in=session.session_signals.values_list('user_id', flat=True)
            )
            print(f'users: {str(users)}')
            # Notify them
            for user in users:
                # update database
                SeatSignal.objects.filter(
                    user=user, 
                    session=session
                ).delete()
                # Contact user
                print(user.phone_num) # temp
                send_signal(session.crn, user.phone_num)

def send_signal(crn, to_number) -> None:
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

