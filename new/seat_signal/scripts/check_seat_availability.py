"""
Check open seat count for a CRN directly against C@B's live details API.
Doesn't touch the DB, so it works even for a crn that hasn't been synced yet.

Usage:
    python -m seat_signal.scripts.check_seat_availability --crn 10036
"""
import argparse

from seat_signal.scripts._bootstrap import setup_django

setup_django()

from core.models import CourseSession
from seat_signal.services import check_seat_availability


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crn", required=True)
    args = parser.parse_args()

    seats = check_seat_availability(CourseSession(crn=args.crn))
    print(f"crn {args.crn}: {seats} seat(s) available")


if __name__ == "__main__":
    main()
