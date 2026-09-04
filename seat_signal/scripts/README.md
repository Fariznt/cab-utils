# seat_signal scripts

Manual CLI probes into the `seat_signal` service layer, for exercising watches
and polling without going through `sms` or the real `poll_seats` loop.

Run from `new/`: `python -m seat_signal.scripts.<name> [args]`

- `create_watch.py` - create a watch (creates user/session if missing)
- `remove_watch.py` - remove a watch
- `list_watches.py` - list a user's active watches
- `check_seat_availability.py` - check a CRN directly against C@B, no DB
- `list_active_sessions.py` - list every session with an active watch
- `poll_once.py` - read-only poll pass, safe to rerun (no deletes/signals)

Pass `-h` to any script for its exact arguments.
