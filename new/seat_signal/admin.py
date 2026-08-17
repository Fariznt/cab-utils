from django.contrib import admin

from seat_signal.models import SeatSignal


@admin.register(SeatSignal)
class SeatSignalAdmin(admin.ModelAdmin):
    list_display = ["user", "session", "datetime_created"]
    list_filter = ["datetime_created"]
