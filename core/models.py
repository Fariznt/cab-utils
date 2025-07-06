from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    phone_num = models.CharField(max_length=16) # TODO: phone number in heavy need of validation

class CourseSession(models.Model):
    crn = models.CharField(max_length=5, primary_key=True)
    code = models.CharField(9)
    section = models.CharField(3)
    sem_id = models.CharField(6)
    title = models.CharField()
