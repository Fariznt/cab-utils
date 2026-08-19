"""
Loads .env so these scripts can read TELNYX_* config directly. No Django setup
here (unlike seat_signal/scripts) since neither script touches models.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name} (set it in .env)")
    return value
