from django.core.management.base import BaseCommand
from core.models import CourseSession
import requests

class Command(BaseCommand):
    help = 'Fetches course data for a given semester ID and updates courses database. ' \
        + '\nE.g. "python manage.py update_db 202410" to update Fall 2025.'

    def add_arguments(self, parser):
        parser.add_argument('search_id', type=int, help=
                            'search_id is a semester identifier 00 (Summer), 10 (Fall), 15 (Winter), or 20 (Spring)' \
                            ' appended to the FIRST year in the corresponding ACADEMIC year (e.g. 2025 for 2025-2026' \
                            ' academic year), or 99999 for four "current" semesters on C@B at once.')

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
        headers = { # look like a browser to CAB's API
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        try:
            response = requests.post(search_url, json=search_payload, headers=headers)
            self.stdout.write(f'Response received: {response}')
            self.stdout.write(f'status: {response.status_code}')
            self.stdout.write(f'headers: {response.headers}')
            self.stdout.write(f'text: {response.text}')
            course_data = response.json()
        except:
            self.stderr.write(self.style.ERROR('Failed to fetch course data'))
            return
        
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