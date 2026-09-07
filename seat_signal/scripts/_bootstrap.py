"""
Lets these scripts run standalone (`python -m seat_signal.scripts.<name>`)
instead of through manage.py, while still using the real models/settings.
"""
import os
from pathlib import Path

import django
from dotenv import load_dotenv


def setup_django():
    # Models can't be imported until this runs, so every script calls this
    # before importing anything from core/seat_signal.
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CAB_Utils.settings.dev")
    django.setup()
