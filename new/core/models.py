from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models.functions import Concat

from core.fields import EncryptedPhoneField
from core.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Phone number is the sole identity, no username. Regular users never get a
    usable password (see UserManager); staff/ops accounts do, for /admin login.
    """
    phone_num = EncryptedPhoneField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    # Flips true on the user's first-ever SeatSignal, so the confirmation
    # message only shows the save-contact/notification tip once.
    has_created_watch = models.BooleanField(default=False)

    USERNAME_FIELD = "phone_num"
    objects = UserManager()

    def __str__(self):
        return f"User #{self.pk}"


class CourseSession(models.Model):
    """One row per (course, section, semester) offering, synced from C@B."""
    crn = models.CharField(max_length=5)
    # Split out of C@B's combined "CSCI 0320" code so future lookups can search
    # on department/course number separately. code below reassembles them for
    # every place that still wants the combined form.
    department_code = models.CharField(max_length=16)
    # Generous width: C@B's code format isn't guaranteed stable across semesters
    # (e.g. cross-listed courses can produce longer codes than a plain "0320").
    course_code = models.CharField(max_length=64)
    code = models.GeneratedField(
        expression=Concat("department_code", models.Value(" "), "course_code"),
        output_field=models.CharField(max_length=64),
        db_persist=True,
    )
    section = models.CharField(max_length=3)
    sem_id = models.CharField(max_length=6)
    title = models.CharField(max_length=255)

    class Meta:
        constraints = [
            # What the poll loop uses to hit C@B's details endpoint.
            models.UniqueConstraint(fields=["crn", "sem_id"], name="unique_crn_sem"),
            # What the SMS conversation uses when a user picks a course.
            models.UniqueConstraint(
                fields=["code", "section", "sem_id"], name="unique_code_section_sem"
            ),
        ]
        indexes = [
            # Backs the pg_trgm similarity search the SMS picking flow uses.
            GinIndex(
                fields=["code", "title"],
                name="coursesession_trgm_idx",
                opclasses=["gin_trgm_ops", "gin_trgm_ops"],
            ),
        ]

    def __str__(self):
        return f"{self.code} {self.section} ({self.sem_id})"


class EventLog(models.Model):
    """Append-only audit log. seat_signal/sms write to it; ops reads from it."""
    EVENT_TYPES = [
        ("account_created", "Account created"),
        ("watch_created", "Watch created"),
        ("watch_removed", "Watch removed"),
        ("sms_received", "SMS received"),
        ("sms_sent", "SMS sent"),
        ("seat_found", "Seat found"),
        ("poll_cycle", "Poll cycle"),
        ("error", "Error"),
    ]

    event_type = models.CharField(max_length=32, choices=EVENT_TYPES)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    session = models.ForeignKey(
        CourseSession, null=True, blank=True, on_delete=models.SET_NULL
    )
    message = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
