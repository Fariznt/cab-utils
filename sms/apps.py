from django.apps import AppConfig


class SmsConfig(AppConfig):
    name = 'sms'

    def ready(self):
        import sms.signals  # noqa: F401 - registers the seat_opened receiver
