# CAB Utils

SMS-based seat-opening alerts for Brown University course registration (C@B) — text a number to watch a course section, get texted back when a seat opens.

## Usage

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in required vars, see comments in the file
docker compose up -d db
python manage.py migrate
python manage.py runserver
```

Management commands:
- `python manage.py update_db <search_id>` — sync `CourseSession`s from C@B for a semester (see `core/management/commands/update_db.py` for `search_id` format).
- `python manage.py poll_seats` — runs the seat-availability poll loop (`seat_signal`); long-running, meant for a supervised process (systemd in prod).

## App structure

One-way dependency graph: `core` ← `seat_signal` ← (`sms`, `ops`).

| App | Purpose |
|---|---|
| `core` | Foundational data: `User` (phone-number identity), `CourseSession` (synced from C@B), `EventLog` (shared audit log). No interface logic. |
| `seat_signal` | Domain logic for watching a course/section and polling C@B for open seats. No views/urls — fires a `seat_opened` signal on notify. |
| `sms` | *(stencil — not yet implemented)* Telnyx-facing webhook + conversation flow; listens for `seat_opened`. |
| `ops` | *(stencil — not yet implemented)* Staff-only log viewer over `core`'s `EventLog`. |

Postgres (via `docker-compose.yml`, service `db`) is required locally — SQLite won't do (`pg_trgm` trigram search, encrypted fields).
