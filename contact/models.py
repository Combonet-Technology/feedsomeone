from django.db import models


# Create your models here.
class Contact(models.Model):
    firstname = models.CharField(max_length=40)
    lastname = models.CharField(max_length=40)
    email = models.EmailField(max_length=40)
    subject = models.CharField(max_length=100)
    message = models.TextField()
    received = models.BooleanField(default=False)
