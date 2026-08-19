"""
Run a single poll pass: check every actively-watched CourseSession against
C@B and report which ones currently have an open seat.

Doesn't delete watches or fire the seat_opened signal - that side of things
lives in the poll_seats management command's loop, not in this service call.

Usage:
    python -m seat_signal.scripts.poll_once
"""
from seat_signal.scripts._bootstrap import setup_django

setup_django()

from seat_signal.services import find_signals_with_open_seats


def main():
    found = list(find_signals_with_open_seats())
    if not found:
        print("No open seats found")
        return
    for session, users in found:
        watchers = ", ".join(str(user) for user in users)
        print(f"{session}: open seat! watchers: {watchers}")


if __name__ == "__main__":
    main()
