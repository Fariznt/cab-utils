"""
Create a SeatSignal watch, creating the user and/or course session first if
they don't already exist.

Usage:
    python -m seat_signal.scripts.create_watch --phone +15551234567 \
        --crn 10036 --sem-id 202410 --code "CSCI 0320" --section S01 [--title "..."]

--code/--section/--title are only required if no CourseSession with that
crn+sem_id already exists.
"""
import argparse

from seat_signal.scripts._bootstrap import setup_django

setup_django()

from core.models import CourseSession, User
from seat_signal.services import SignalCapExceeded, create_watch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone", required=True, help="E.164 phone number, e.g. +15551234567")
    parser.add_argument("--crn", required=True)
    parser.add_argument("--sem-id", required=True)
    parser.add_argument("--code", help="Required if the CourseSession doesn't exist yet")
    parser.add_argument("--section", help="Required if the CourseSession doesn't exist yet")
    parser.add_argument("--title", default="", help="Required if the CourseSession doesn't exist yet")
    args = parser.parse_args()

    user = User.objects.filter(phone_num=args.phone).first()
    if user is None:
        user = User.objects.create_user(phone_num=args.phone)
        print(f"Created user {user}")

    session = CourseSession.objects.filter(crn=args.crn, sem_id=args.sem_id).first()
    if session is None:
        if not (args.code and args.section):
            parser.error("--code and --section are required to create a new CourseSession")
        session = CourseSession.objects.create(
            crn=args.crn, sem_id=args.sem_id, code=args.code, section=args.section, title=args.title,
        )
        print(f"Created course session {session}")

    try:
        watch = create_watch(user, session)
    except SignalCapExceeded as e:
        print(f"FAILED: {e}")
        return
    print(f"Watch created: {watch}")


if __name__ == "__main__":
    main()
