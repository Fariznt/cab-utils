"""
match_course and match_section, called directly.

The catalog is real Fall 2026 C@B rows, picked for the cases that bite: numbers
that collide once padding zeros come off (CSCI 0220/2200, HIAA 0010/0100), codes
that differ only by a trailing letter (CSCI 0111/0111E), courses with one kind of
section and courses with several, and sections C@B never numbered.
"""

from django.test import TestCase

from core.models import CourseSession
from seat_signal.utils import get_current_sem_id
from sms.match_utils import match_course, match_section

SEM_ID = get_current_sem_id()
OTHER_SEM_ID = "209910"

# (department_code, course_code, title, sections)
CATALOG = [
    ("CSCI", "0111", "Computing Foundations: Data", ["S01", "L01", "L02"]),
    ("CSCI", "0111E", "Data-Centric Intro to Computing and Coding Agents", ["S01", "L01"]),
    ("CSCI", "0220", "Introduction to Discrete Structures and Probability", ["S01", "C01", "C02"]),
    ("CSCI", "0320", "Introduction to Software Engineering", ["S01", "S02", "C01", "C02"]),
    ("CSCI", "1951R", "Introduction to Robotics", ["S01"]),
    ("CSCI", "2200", "Cybersecurity Law and Policy", ["S01", "S02"]),
    ("CHEM", "0330L", "Equilibrium, Rate, and Structure Laboratory", ["L01", "L02", "L10"]),
    ("CHIN", "0100", "Basic Chinese", ["S01", "S02", "S03", "S04"]),
    ("HIAA", "0010", "A Global History of Art and Architecture", ["S01", "C01"]),
    ("HIAA", "0100", "Introduction to Architectural Design Studio", ["S01"]),
    ("MUSC", "0021F", "Popular Music and Society in Latin America", ["S01"]),
    # C@B leaves independent studies unnumbered: their section is blank
    ("AMST", "1907C", "James Baldwin (ENGL 1711S)", [""]),
]


class CatalogTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        crn = 10000
        for department_code, course_code, title, sections in CATALOG:
            for section in sections:
                CourseSession.objects.create(
                    crn=str(crn), department_code=department_code, course_code=course_code,
                    section=section, sem_id=SEM_ID, title=title,
                )
                crn += 1


class DepartmentTests(CatalogTestCase):
    """The letters half of a code. Exact, or a listed alias."""

    def test_real_department_code(self):
        self.assertEqual(match_course("CSCI 0320", SEM_ID), "CSCI 0320")

    def test_case_and_internal_spacing_are_ignored(self):
        for text in ["csci 0320", "CSCI0320", "cSci   0320"]:
            with self.subTest(text=text):
                self.assertEqual(match_course(text, SEM_ID), "CSCI 0320")

    def test_alias_resolves_to_the_real_department(self):
        self.assertEqual(match_course("CS 320", SEM_ID), "CSCI 0320")
        self.assertEqual(match_course("comp 320", SEM_ID), "CSCI 0320")
        self.assertEqual(match_course("mus 21f", SEM_ID), "MUSC 0021F")

    def test_misspelled_department_is_not_guessed_at(self):
        self.assertIsNone(match_course("CSIC 320", SEM_ID))

    def test_unlisted_department(self):
        self.assertIsNone(match_course("ZZZ 100", SEM_ID))

    def test_department_from_another_semester(self):
        CourseSession.objects.create(
            crn="99999", department_code="PHIL", course_code="0010",
            section="S01", sem_id=OTHER_SEM_ID, title="Ancient Philosophy",
        )
        self.assertIsNone(match_course("PHIL 0010", SEM_ID))


class CourseCodeTests(CatalogTestCase):
    """The digits half. Exact once padding zeros come off either end."""

    def test_leading_zeros_are_optional(self):
        for text in ["CSCI 0320", "CSCI 320"]:
            with self.subTest(text=text):
                self.assertEqual(match_course(text, SEM_ID), "CSCI 0320")

    def test_trailing_zeros_are_optional(self):
        for text in ["CSCI 032", "CSCI 32"]:
            with self.subTest(text=text):
                self.assertEqual(match_course(text, SEM_ID), "CSCI 0320")

    def test_a_wrong_digit_in_the_middle_is_not_forgiven(self):
        self.assertIsNone(match_course("CSCI 0325", SEM_ID))

    def test_number_the_department_does_not_offer(self):
        self.assertIsNone(match_course("CSCI 8888", SEM_ID))

    def test_trailing_letter_separates_two_courses_sharing_a_number(self):
        self.assertEqual(match_course("CSCI 0111", SEM_ID), "CSCI 0111")
        self.assertEqual(match_course("CSCI 0111E", SEM_ID), "CSCI 0111E")
        self.assertEqual(match_course("csci 111e", SEM_ID), "CSCI 0111E")

    def test_four_digit_number_with_a_trailing_letter(self):
        self.assertEqual(match_course("csci 1951r", SEM_ID), "CSCI 1951R")

    def test_collision_is_broken_by_the_zeros_the_student_typed(self):
        # CSCI 0220 and CSCI 2200 both strip to "22"
        self.assertEqual(match_course("CSCI 0220", SEM_ID), "CSCI 0220")
        self.assertEqual(match_course("CSCI 220", SEM_ID), "CSCI 0220")
        self.assertEqual(match_course("CSCI 2200", SEM_ID), "CSCI 2200")
        # HIAA 0010 and HIAA 0100 both strip to "1"
        self.assertEqual(match_course("HIAA 10", SEM_ID), "HIAA 0010")
        self.assertEqual(match_course("HIAA 100", SEM_ID), "HIAA 0100")

    def test_collision_the_zeros_cannot_break_falls_to_the_lower_number(self):
        self.assertEqual(match_course("CSCI 22", SEM_ID), "CSCI 0220")
        self.assertEqual(match_course("HIAA 1", SEM_ID), "HIAA 0010")


class TitleTests(CatalogTestCase):
    """Anything not code-shaped goes to trigram similarity."""

    def test_full_title(self):
        self.assertEqual(
            match_course("Introduction to Software Engineering", SEM_ID), "CSCI 0320"
        )

    def test_partial_title(self):
        self.assertEqual(match_course("software engineering", SEM_ID), "CSCI 0320")

    def test_loosely_typed_title(self):
        self.assertEqual(match_course("discrete structures", SEM_ID), "CSCI 0220")

    def test_title_from_another_semester(self):
        self.assertIsNone(match_course("software engineering", OTHER_SEM_ID))

    def test_unrelated_text(self):
        self.assertIsNone(match_course("zzzzqqq nonsense", SEM_ID))

    def test_empty_text(self):
        self.assertIsNone(match_course("", SEM_ID))


class SectionTests(CatalogTestCase):
    """A section reply against the sections one course actually offers."""

    def test_exact_section_code(self):
        self.assertEqual(match_section("S01", "CSCI 0320", SEM_ID), "S01")

    def test_padding_zero_and_internal_space_are_optional(self):
        for text in ["S1", "s1", "S 1", "s 01"]:
            with self.subTest(text=text):
                self.assertEqual(match_section(text, "CSCI 0320", SEM_ID), "S01")

    def test_two_digit_section_number(self):
        self.assertEqual(match_section("l10", "CHEM 0330L", SEM_ID), "L10")

    def test_section_letters_other_than_s(self):
        self.assertEqual(match_section("C2", "CSCI 0320", SEM_ID), "C02")
        self.assertEqual(match_section("L01", "CSCI 0111", SEM_ID), "L01")

    def test_wrong_letter_is_forgiven_when_the_course_has_one_kind(self):
        # CSCI 2200 runs S01/S02 only, so "L2" can only have meant S02
        self.assertEqual(match_section("L2", "CSCI 2200", SEM_ID), "S02")

    def test_bare_number_works_when_the_course_has_one_kind(self):
        for text in ["3", "03"]:
            with self.subTest(text=text):
                self.assertEqual(match_section(text, "CHIN 0100", SEM_ID), "S03")

    def test_wrong_letter_is_not_forgiven_when_the_course_mixes_kinds(self):
        self.assertIsNone(match_section("L01", "CSCI 0320", SEM_ID))

    def test_bare_number_is_ambiguous_when_the_course_mixes_kinds(self):
        self.assertIsNone(match_section("1", "CSCI 0320", SEM_ID))

    def test_section_the_course_does_not_offer(self):
        self.assertIsNone(match_section("S99", "CSCI 0320", SEM_ID))

    def test_text_that_is_not_a_section_code(self):
        for text in ["the first one", "", "S001", "SS1"]:
            with self.subTest(text=text):
                self.assertIsNone(match_section(text, "CSCI 0320", SEM_ID))

    def test_course_whose_sections_are_all_unnumbered(self):
        self.assertIsNone(match_section("S01", "AMST 1907C", SEM_ID))

    def test_course_from_another_semester(self):
        self.assertIsNone(match_section("S01", "CSCI 0320", OTHER_SEM_ID))
