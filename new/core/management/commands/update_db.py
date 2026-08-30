import logging

import requests
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from core.models import CourseSession

logger = logging.getLogger(__name__)

# Reverse-engineered C@B search endpoint; needs a browser User-Agent to respond normally.
SEARCH_URL = "https://cab.brown.edu/api/?page=fose&route=search&is_ind_study=N&is_canc=N"
SPOOFED_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 "
        "Safari/537.36"
    ),
}


class Command(BaseCommand):
    help = (
        "Fetches course data for a given semester ID and updates the course database. "
        'E.g. "python manage.py update_db 202410" to update Fall 2025, or 99999 for '
        "all current semesters."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "search_id", type=int,
            help="Semester identifier (see seat_signal/utils.py for the id format), or 99999 for current semesters.",
        )

    def handle(self, *args, **options):
        search_id = options["search_id"]
        self.stdout.write(f"Fetching course data for search_id={search_id}")

        search_payload = {
            "other": {"srcdb": search_id},
            "criteria": [
                {"field": "is_ind_study", "value": "N"},
                {"field": "is_canc", "value": "N"},
            ],
        }
        try:
            response = requests.post(SEARCH_URL, json=search_payload, headers=SPOOFED_HEADERS)
            response.raise_for_status()
            course_data = response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch course data: {e}")
            self.stderr.write(self.style.ERROR(f"Failed to fetch course data: {e}"))
            return

        rows = [
            (cd.get("crn"), cd.get("code"), cd.get("no"), cd.get("srcdb"), cd.get("title"))
            for cd in course_data["results"]
        ]

        # Batched insert in one transaction, roughly 200x faster than per-row
        # ORM get_or_create().
        # ON CONFLICT DO NOTHING against (crn, sem_id): CourseSession's PK is
        # a surrogate id (crn alone isn't unique across semesters), so re-running
        # this for a semester already synced just skips already-known rows.
        table = CourseSession._meta.db_table
        sql = f"""
            INSERT INTO {table} (crn, code, section, sem_id, title)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (crn, sem_id) DO NOTHING
        """
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.executemany(sql, rows)

        logger.info(f"update_db complete: search_id={search_id}, {len(rows)} rows fetched")
        self.stdout.write(self.style.SUCCESS(f"Database update complete ({len(rows)} rows fetched)."))
