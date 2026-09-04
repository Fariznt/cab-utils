from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from core.models import CourseSession, EventLog, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # No username/first/last name/email fields on this model, phone_num
    # is the only identity field, so the default UserAdmin fieldsets don't apply.
    ordering = ["id"]
    list_display = ["id", "is_staff", "is_active", "date_joined"]
    fieldsets = (
        (None, {"fields": ("phone_num", "password")}),
        ("Permissions", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"fields": ("phone_num", "password1", "password2")}),
    )
    # No search_fields: phone_num is encrypted at rest, so icontains search
    # against it would run against ciphertext and never match anything useful.


@admin.register(CourseSession)
class CourseSessionAdmin(admin.ModelAdmin):
    list_display = ["code", "section", "sem_id", "title", "crn"]
    search_fields = ["code", "title", "crn"]
    list_filter = ["sem_id"]


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ["event_type", "level", "user", "session", "created_at"]
    list_filter = ["event_type", "level"]
    readonly_fields = [f.name for f in EventLog._meta.fields]
