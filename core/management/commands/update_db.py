from django.core.management.base import BaseCommand
from core.models import CourseSession
import requests

class Command(BaseCommand):
    help = 'Fetches course data for a given semester ID and updates courses database. ' \
        + '\nE.g. "python manage.py update_db 202410" to update Fall 2025.'

    def add_arguments(self, parser):
        parser.add_argument('search_id', type=int, help=
                            'search_id is a semester identifier 00 (Summer), 10 (Fall), 15 (Winter), or 20 (Spring)' \
                            ' appended to the year, or 99999 for four "current" semesters on C@B at once.')

    def handle(self, *args, **options):
        self.stdout.write("Beginning database update")

        search_id = options['search_id']

        # Fetch given semester's courses
        search_payload = {
            "other": {
                "srcdb": search_id
            },
            "criteria": [
                {
                "field": "is_ind_study",
                "value": "N"
                },
                {
                "field": "is_canc",
                "value": "N"
                }
            ]
        }
        search_url = 'https://cab.brown.edu/api/?page=fose&route=search&is_ind_study=N&is_canc=N'
        try:
            response = requests.post(search_url, json=search_payload)
            course_data = response.json()
        except:
            self.stderr.write(self.style.ERROR('Failed to fetch course data'))
        
        # add relevant info to app database
        for course_datum in course_data['results']:
            crn = course_datum.get('crn')
            code = course_datum.get('code')
            section = course_datum.get('no')
            title = course_datum.get('title')
            sem_id = course_datum.get('srcdb')
            new_session = CourseSession(crn=crn, code=code, section=section, sem_id=sem_id, title = title)
            new_session.save()

        self.stdout.write("Database update complete.")        