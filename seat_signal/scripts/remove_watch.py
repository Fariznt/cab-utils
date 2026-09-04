"""
Remove a SeatSignal watch.

Usage:
    python -m seat_signal.scripts.remove_watch --phone +15551234567 --crn 10036 --sem-id 202410
"""
import argparse

from seat_signal.scripts._bootstrap import setup_django

setup_django()

from core.models import CourseSession, User
from seat_signal.services import remove_watch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--crn", required=True)
    parser.add_argument("--sem-id", required=True)
    args = parser.parse_args()

    user = User.objects.filter(phone_num=args.phone).first()
    if user is None:
        parser.error(f"No user with phone {args.phone}")

    session = CourseSession.objects.filter(crn=args.crn, sem_id=args.sem_id).first()
    if session is None:
        parser.error(f"No CourseSession with crn={args.crn} sem_id={args.sem_id}")

    removed = remove_watch(user, session)
    print("Watch removed" if removed else "No matching watch found")


if __name__ == "__main__":
    main()
