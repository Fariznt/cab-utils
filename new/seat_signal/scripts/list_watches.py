"""
List a user's active SeatSignal watches.

Usage:
    python -m seat_signal.scripts.list_watches --phone +15551234567
"""
import argparse

from seat_signal.scripts._bootstrap import setup_django

setup_django()

from core.models import User
from seat_signal.services import get_watches_for_user


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone", required=True)
    args = parser.parse_args()

    user = User.objects.filter(phone_num=args.phone).first()
    if user is None:
        parser.error(f"No user with phone {args.phone}")

    watches = list(get_watches_for_user(user))
    if not watches:
        print("No active watches")
        return
    for watch in watches:
        print(f"{watch.session} (watching since {watch.datetime_created})")


if __name__ == "__main__":
    main()
