"""
Semester-id conversions. Ported verbatim from legacy/seat_signal/utils.py — this
is reverse-engineered domain knowledge about C@B, not implementation choice.

Semester id = 4-digit academic-year start year + 2-digit term code
('15'=Winter, '20'=Spring, '00'=Summer, '10'=Fall). Winter/Spring belong to the
*second* calendar year of the academic year (e.g. '202415' = Winter, calendar
year 2025) — a recurring source of off-by-one bugs, so this logic is pinned
down by tests in seat_signal/tests.py.
"""

TERM_NAMES = {
    "15": "Winter",
    "20": "Spring",
    "00": "Summer",
    "10": "Fall",
}
TERM_IDS = {name: code for code, name in TERM_NAMES.items()}
TERM_RANK = {"15": 0, "20": 1, "00": 2, "10": 3}
SHIFTED_TERMS = {"15", "20"}  # Winter, Spring (by term code)
SHIFTED_TERM_NAMES = {"Winter", "Spring"}  # same, by term name


def get_recent_sems(sem_ids: list[str], n: int = 4) -> list[tuple[str, str]]:
    """Takes a list of semester ids and returns the n most recent as (id, readable name) tuples."""

    def sort_key(sem_id: str):
        academic_year = int(sem_id[:4])
        term = sem_id[4:]
        calendar_year = academic_year + 1 if term in SHIFTED_TERMS else academic_year
        return (calendar_year, TERM_RANK[term])

    recent_ids = sorted(sem_ids, key=sort_key, reverse=True)[:n]
    return [(sem_id, get_sem_str(sem_id)) for sem_id in recent_ids]


def get_sem_str(sem_id: str) -> str:
    """Converts a semester id (e.g. '202510') to a readable string (e.g. 'Fall 2025')."""
    academic_year = int(sem_id[:4])
    term_code = sem_id[4:]
    term = TERM_NAMES[term_code]
    year = academic_year + 1 if term_code in SHIFTED_TERMS else academic_year
    return f"{term} {year}"


def get_sem_id(sem_str: str) -> str:
    """Converts a readable semester string (e.g. 'Fall 2025') to a semester id."""
    term, year = sem_str.split()
    year = int(year)
    term_id = TERM_IDS[term]
    academic_year = year - 1 if term in SHIFTED_TERM_NAMES else year
    return f"{academic_year}{term_id}"
