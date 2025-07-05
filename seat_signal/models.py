from django.db import models
from core.models import User, CourseSession

class SeatSignal(models.Model):
    """Represents a User watching a specific CourseSession for seats"""
    # TODO remove temp comment: number defined separately because user can be none. user exists to allow manipulating the call
    user = models.ForeignKey(User, on_delete=models.CASCADE) # TODO: null=True when exposed as an API. 
    # save number separateyl when exposed as an API. will allow it to work without users.
    
    session = models.ForeignKey(CourseSession, on_delete=models.PROTECT)
    datetime_created = models.DateTimeField(auto_now_add=True)
    
    