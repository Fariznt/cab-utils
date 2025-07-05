from background_task import background
from background_task.models import Task
import requests
import json
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from core.models import CourseSession

# look at documentation to figure out django-background_tasks
# TODO: error handling, exceptions, logging failures, etc.
@background(schedule=0) # begin immediately, repeat every 30 seconds
def watch_task(crn, number, contact_method, repeat=10, repeat_until=None):
    """Polls the C@B API to check for seat availability. If there's a seat, contacts the user."""

    # Get course session details from C@B's API
    payload = {
        'key': 'crn:' + crn
    }
    url = "https://cab.brown.edu/api/?page=fose&route=details"
    response = requests.post(url, json=payload)
    course_details = response.json()

    seats = extract_seat_count(course_details) # Get seat count for this session

    if seats != 0:
        complete_task = Task.objects.filter(
            task_name = 'watch_task',
            task_params = json.dumps([crn, number])
        )
        complete_task.delete()
        send_signal(crn, number, contact_method)


def extract_seat_count(course_details: dict[str, any]) -> int:
    """Extracts from a JSON of course session details the number of available seats"""
    return 0

def send_signal(crn, number, contact_method) -> None:
    """Notifies the user (by text/call) of an open seat in the session they had SeatSignal watching"""
    if contact_method == 'call':
        # Create call voice message string
        session = CourseSession.objects.get(crn=crn)
        course_name = session.name
        section = session.section
        msg = (
            f"Seat Signal has detected an open seat for {course_name} "
            f"<break time='0.1s'/> section {section}."
            "<break time='0.3s'/> Proceed to registration."
        )
        # Create call voice message
        voice_resp = VoiceResponse()
        voice_resp.pause(length=1.5)
        voice_resp.say(msg, voice="alice")
        # Create client & call
        # client = Client(ACCOUNT_SID, AUTH_TOKEN)
        # call = client.calls.create(
        #     to="", 
        #     from_="",
        #     twiml = resp.to_xml()
        # )

    #do texting later
    pass # TBD
    