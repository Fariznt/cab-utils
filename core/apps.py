from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Registers the EventLog -> logging bridge (see core/signals.py).
        from core import signals  # noqa: F401
