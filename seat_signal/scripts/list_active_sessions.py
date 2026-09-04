"""
List every CourseSession that currently has at least one active watch.

Usage:
    python -m seat_signal.scripts.list_active_sessions
"""
from seat_signal.scripts._bootstrap import setup_django

setup_django()

from seat_signal.services import get_sessions_with_active_signals


def main():
    sessions = list(get_sessions_with_active_signals())
    if not sessions:
        print("No sessions currently being watched")
        return
    for session in sessions:
        print(session)


if __name__ == "__main__":
    main()
