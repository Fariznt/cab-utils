from background_task import background
from background_task.models import Task
import requests
import json

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
    pass # TBD
    