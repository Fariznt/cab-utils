from django.contrib import admin
from seat_signal.models import SeatSignal

@admin.register(SeatSignal)
class SeatSignalAdmin(admin.ModelAdmin):
    pass