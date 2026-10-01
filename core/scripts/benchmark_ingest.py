"""
Times update_db's ingestion path against the two alternatives it could have
used, on a real semester of C@B data.

Rows go in under a throwaway sem_id and are deleted afterwards, so a run never
touches real synced data. Results: core/scripts/README.md.

Usage:
    python -m core.scripts.benchmark_ingest [search_id] [--runs N]
"""
from core.scripts._bootstrap import setup_django

setup_django()

import argparse
import statistics
from time import perf_counter

from core.management.commands.update_db import bulk_insert, fetch_rows
from core.models import CourseSession

# Throwaway semester id, so a run can't collide with (or delete) synced rows.
BENCH_SEM_ID = "999998"


def orm_bulk_create(rows):
    """Django's own batched insert: the ORM-idiomatic alternative to the raw SQL."""
    sessions = [
        CourseSession(
            crn=crn, department_code=department_code, course_code=course_code,
            section=section, sem_id=sem_id, title=title,
        )
        for crn, department_code, course_code, section, sem_id, title in rows
    ]
    CourseSession.objects.bulk_create(sessions, ignore_conflicts=True)


def orm_get_or_create(rows):
    """
    Legacy's pre-optimization path: two queries and one transaction per row.
    Reconstructed, since the original predates this repo's history.
    """
    for crn, department_code, course_code, section, sem_id, title in rows:
        CourseSession.objects.get_or_create(
            crn=crn, sem_id=sem_id,
            defaults={
                "department_code": department_code, "course_code": course_code,
                "section": section, "title": title,
            },
        )


def clear_bench_rows():
    CourseSession.objects.filter(sem_id=BENCH_SEM_ID).delete()


def time_run(insert_fn, rows, preload):
    """One timed insert into an empty table, or into a full one if preload."""
    clear_bench_rows()
    if preload:
        # Re-sync case: every row is already there, so every insert conflicts.
        bulk_insert(rows)
    start = perf_counter()
    insert_fn(rows)
    return perf_counter() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("search_id", nargs="?", type=int, default=202410, help="Semester to pull test data from.")
    parser.add_argument("--runs", type=int, default=3, help="Timed runs per variant; the median is reported.")
    args = parser.parse_args()

    start = perf_counter()
    rows = fetch_rows(args.search_id)
    fetch_secs = perf_counter() - start
    # Every variant inserts identical data, under the throwaway semester id.
    rows = [
        (crn, department_code, course_code, section, BENCH_SEM_ID, title)
        for crn, department_code, course_code, section, _, title in rows
    ]
    print(f"search_id={args.search_id}: fetched {len(rows)} rows from C@B in {fetch_secs:.2f}s")
    print(f"{args.runs} runs per variant, median reported\n")

    variants = [
        ("raw executemany (update_db)", bulk_insert, False),
        ("raw executemany, re-sync", bulk_insert, True),
        ("ORM bulk_create", orm_bulk_create, False),
        ("ORM get_or_create per row", orm_get_or_create, False),
    ]
    try:
        for name, insert_fn, preload in variants:
            times = [time_run(insert_fn, rows, preload) for _ in range(args.runs)]
            median = statistics.median(times)
            all_runs = ", ".join(f"{t:.3f}" for t in times)
            print(f"{name:<28} {median:8.3f}s median  {len(rows) / median:>9,.0f} rows/s   runs: {all_runs}")
    finally:
        clear_bench_rows()


if __name__ == "__main__":
    main()
