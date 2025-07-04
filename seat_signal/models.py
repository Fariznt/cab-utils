from django.db import models
from core.models import User, CourseSession

class SeatSignal(models.Model):
    """Represents a User watching a specific CourseSession for seats"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.ForeignKey(CourseSession, on_delete=models.PROTECT)
    datetime_created = models.DateTimeField(auto_now_add=True)
    
    