from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    phone_num = models.CharField(max_length=16) # TODO: phone number in heavy need of validation