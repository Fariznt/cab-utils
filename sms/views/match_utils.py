"""
Resolving a student's free text to a real course or section.

Text arrives here already stripped (see _handle_state_message), and nothing here
writes to the database or decides what happens next.
"""

import re

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest

from core.models import CourseSession

# Trigram score a title has to beat to count as a match. Postgres' own default:
# low enough for a partial title, high enough that unrelated text matches nothing.
COURSE_MATCH_THRESHOLD = 0.3

# Shorthands students type for a department, mapped to C@B's real code. Add
# freely; only 2-4 letter keys are reachable, since that's what match_course's
# course code pattern accepts.
DEPARTMENT_ALIASES = {
    "CS": "CSCI",
    "BIO": "BIOL",
    "MUS": "MUSC",
    "POL": "POLS",
    "SOCI": "SOC",
    "ENGI": "ENGN",
    "MAT": "MATH",
}


def match_course(text, sem_id):
    """
    Resolves free text to a course code like "CSCI 0320", or None. Text shaped
    like a code (2-4 letters then 1-4 digits and an optional letter) is matched
    department then number; anything else is treated as a title.
    """
    def strip_zeros(course_code):
        """Padding zeros at either end, never the middle: 0320, 320 and 32 all give 32."""
        return course_code.strip("0") or "0"

    parsed = re.fullmatch(r"([A-Za-z]{2,4})\s*(\d{1,4}[A-Za-z]?)", text)
    if parsed is None:
        return (
            CourseSession.objects.filter(sem_id=sem_id)
            .annotate(
                similarity=Greatest(
                    TrigramSimilarity("code", text), TrigramSimilarity("title", text)
                )
            )
            .filter(similarity__gte=COURSE_MATCH_THRESHOLD)
            .order_by("-similarity")
            .values_list("code", flat=True)
            .first()
        )

    letters, number = (group.upper() for group in parsed.groups())
    department_code = DEPARTMENT_ALIASES.get(letters, letters)
    candidates = (
        CourseSession.objects.filter(sem_id=sem_id, department_code=department_code)
        .values_list("course_code", flat=True)
        .distinct()
    )
    matches = sorted(c for c in candidates if strip_zeros(c) == strip_zeros(number))
    if not matches:
        return None

    # Stripping makes real pairs collide (CSCI 0220 and CSCI 2200 both give 22).
    # The zeros the student did or didn't type break the tie, else the lower
    # course number wins.
    best = next((c for c in matches if number.rjust(len(c), "0") == c), matches[0])
    return f"{department_code} {best}"


def match_section(text, code, sem_id):
    """
    Resolves free text to a real section of an already-picked course, or None.
    Exact matches only, allowing for a padding zero the student left out.
    """
    parsed = re.fullmatch(r"([A-Za-z])?\s*(\d{1,2})", text)
    if parsed is None:
        return None
    letter, number = parsed.groups()

    sections = CourseSession.objects.filter(code=code, sem_id=sem_id).values_list(
        "section", flat=True
    )
    # C@B leaves some sections unnumbered (independent studies use an
    # instructor's initials); those can never match a numbered reply.
    numbered = sorted(s for s in sections if re.fullmatch(r"[A-Za-z]\d{1,2}", s))

    if letter:
        typed = f"{letter.upper()}{number}"
        for section in numbered:
            if typed in (section, section[0] + section[1:].lstrip("0")):
                return section

    # A wrong letter, or none at all, is still unambiguous when the course runs
    # only one kind of section.
    if len({section[0] for section in numbered}) == 1:
        for section in numbered:
            if number in (section[1:], section[1:].lstrip("0")):
                return section
    return None
