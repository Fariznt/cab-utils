# CAB Utils

SMS seat alerts for Brown University course registration (C@B). Text the number, pick a course section, and get a text when a seat opens.

C@B has no public API. This project talks to its internal endpoints directly, as reverse-engineered from the network calls the C@B site makes.

## Architecture

Django + DRF, Postgres, Telnyx for SMS. Four apps with a one-way dependency graph: `core` ← `seat_signal` ← (`sms`, `ops`).

| App | Purpose |
|---|---|
| `core` | `User` (phone number as identity, AES-SIV encrypted), `CourseSession` (synced from C@B), `EventLog` (shared audit log). |
| `seat_signal` | Watch logic and the `poll_seats` loop that checks C@B for open seats. Fires a `seat_opened` signal and knows nothing about SMS. |
| `sms` | Telnyx webhook, the rule-based conversation flow, and the `seat_opened` receiver that sends the alert. |
| `ops` | Placeholder for a staff-only view over `EventLog`. |

`/healthz/` reports whether the poll loop's heartbeat is recent.

## Usage

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # fill in, see comments in the file
./run-dev               # Postgres, migrations, poll loop, Cloudflare tunnel, dev server
```

- `python manage.py update_db <search_id>` syncs a semester's sections from C@B (`999999` for all current semesters).
- `python manage.py poll_seats` runs the seat-check loop.

### Building something else on C@B

This repo works as a starting point for other C@B tools. The C@B-specific pieces are already done and independent of Seat Signal:

- **Course data**: `update_db` pulls every section of a semester into Postgres in one batched insert. `CourseSession` is the table to extend.
- **Seat details**: `check_seat_availability` in `seat_signal/services.py` shows how to query C@B's details endpoint for a single section.
- **Semester IDs**: `seat_signal/utils.py` converts between C@B's semester IDs and labels like "Fall 2025".
