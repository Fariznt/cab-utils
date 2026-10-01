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


def fetch_rows(search_id):
    """Fetches a semester's offerings from C@B, flattened into insert-ready tuples."""
    search_payload = {
        "other": {"srcdb": search_id},
        "criteria": [
            {"field": "is_ind_study", "value": "N"},
            {"field": "is_canc", "value": "N"},
        ],
    }
    response = requests.post(SEARCH_URL, json=search_payload, headers=SPOOFED_HEADERS, timeout=(5, 15))
    response.raise_for_status()

    rows = []
    for cd in response.json()["results"]:
        # C@B's code comes back as one combined string, e.g. "CSCI 0320".
        # Split on the first space only, so anything unusual after the
        # department (e.g. a cross-listed code) stays intact in course_code.
        department_code, _, course_code = cd.get("code", "").partition(" ")
        rows.append((
            cd.get("crn"), department_code, course_code,
            cd.get("no"), cd.get("srcdb"), cd.get("title"),
        ))
    return rows


def bulk_insert(rows):
    """
    Batched insert in one transaction, far faster than per-row ORM
    get_or_create().

    ON CONFLICT DO NOTHING against (crn, sem_id): CourseSession's PK is a
    surrogate id (crn alone isn't unique across semesters), so re-running this
    for a semester already synced just skips already-known rows.
    """
    table = CourseSession._meta.db_table
    sql = f"""
        INSERT INTO {table} (crn, department_code, course_code, section, sem_id, title)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (crn, sem_id) DO NOTHING
    """
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.executemany(sql, rows)


class Command(BaseCommand):
    help = (
        "Fetches course data for a given semester ID and updates the course database. "
        'E.g. "python manage.py update_db 202410" to update Fall 2025, or 999999 for '
        "all current semesters."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "search_id", type=int,
            help="Semester identifier (see seat_signal/utils.py for the id format), or 999999 for current semesters.",
        )

    def handle(self, *args, **options):
        search_id = options["search_id"]
        self.stdout.write(f"Fetching course data for search_id={search_id}")

        try:
            rows = fetch_rows(search_id)
        except requests.RequestException as e:
            logger.error(f"Failed to fetch course data: {e}")
            self.stderr.write(self.style.ERROR(f"Failed to fetch course data: {e}"))
            return

        bulk_insert(rows)

        logger.info(f"update_db complete: search_id={search_id}, {len(rows)} rows fetched")
        self.stdout.write(self.style.SUCCESS(f"Database update complete ({len(rows)} rows fetched)."))
