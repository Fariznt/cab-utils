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

@background(schedule=0) # begin immediately, repeat every 10 seconds
def watch_task(crn, number, contact_method, repeat=10, repeat_until=None):
    """Polls the C@B API to check for seat availability. If there's a seat, contacts the user."""

    # Get course session details from C@B's API
    payload = {
        'key': 'crn:' + crn
    }
    url = "https://cab.brown.edu/api/?page=fose&route=details"
    response = requests.post(url, json=payload)
    course_details = response.json()

    # Get seat count for this session as a string; empty string if uncapped
    seats_string = course_details['seats'].partition('<span class="seats_avail">')[2].partition('</span>')[0]

    if seats_string == "" or seats_string != "0":
        Task.objects.filter(
            task_name = 'watch_task',
            task_params = json.dumps([crn, number])
        ).delete()

        # Update seat signal database
        SeatSignal.objects.filter(
            user=User.objects.get(phone_num=number), 
            session=CourseSession.objects.get(crn=crn)
        ).delete()

        # Contact user
        send_signal(crn, number, contact_method)

    # else: continue watching for open seats

def send_signal(crn, to_number, contact_method) -> None:
    """Notifies the user (by text/call) of an open seat in the session they had SeatSignal watching"""
    if contact_method == 'call':
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
    elif contact_method == 'text':
        pass #Not currently supported. If statement exists only to provide infrastructure for later addition