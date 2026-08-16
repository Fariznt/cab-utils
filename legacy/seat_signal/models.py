from django.db import models
from core.models import User, CourseSession

class SeatSignal(models.Model):
    """Represents a User watching a specific CourseSession for seats"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_signals')
    session = models.ForeignKey(CourseSession, on_delete=models.PROTECT, related_name='session_signals')
    datetime_created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'session'],
                name='unique_user_session_signal'
            )
        ]