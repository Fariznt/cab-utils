# core scripts

Run from the repo root: `python -m core.scripts.<name> [-h]`

- `benchmark_ingest.py` - times `update_db`'s insert path against the alternatives, on real C@B data. Inserts under a throwaway `sem_id` and cleans up after itself, so it's safe to run against a live dev DB.

## Ingestion benchmark

Fall 2025 (`search_id=202410`), 6,794 rows, 3 runs per variant, median reported:

| Insert path | Time | Rows/s |
|---|---|---|
| ORM `bulk_create(ignore_conflicts=True)` | 0.29s | 23,100 |
| raw `executemany` + `ON CONFLICT DO NOTHING` (what `update_db` does) | 0.39s | 17,600 |
| same, re-syncing an already-synced semester (every row conflicts) | 0.22s | 31,100 |
| per-row `get_or_create()` (the pre-optimization legacy path) | 28.83s | 236 |

Two findings:

- **Batching is worth ~75x** over per-row `get_or_create()` - 28.8s down to 0.39s for one semester.
- **Raw SQL isn't what buys it.** `bulk_create` lands in the same range (slightly ahead here), so the raw `executemany` isn't paying for itself on speed alone.

Fetching from C@B takes ~8s, so the network dominates either way: a full semester sync is ~8.4s, under half a second of which is the insert.

Environment: Postgres 16.15 (Docker, localhost), Django 6.1 / psycopg 3.3.4, Python 3.14.6, Ryzen 9 8945HS. The per-row variant is reconstructed - it predates this repo's history.

This benchmark and scripts were LLM generated and were not as closely reviewed as the rest of the repo outside of script directories.
