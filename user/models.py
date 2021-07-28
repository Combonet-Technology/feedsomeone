from django.db import models
from django.contrib.auth.models import User
from PIL import Image

# Create your models here.
from django.utils import timezone


# TODO add user ipaddress information for security
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='default.png', upload_to='profile_pics')
    phone_number = models.CharField(max_length=15, null=True)
    facebook = models.CharField(max_length=100, null=True, default="#")
    instagram = models.CharField(max_length=100, null=True, default="#")
    twitter = models.CharField(max_length=100, null=True, default="#")
    state = models.CharField(max_length=30, null=True)
    country = models.CharField(max_length=30, null=True)
    short_bio = models.CharField(max_length=100, null=False, default='replace with a short introduction about yourself')
    reason_joined = models.TextField(null=False, default='The burden to help the needy has never been more than now')
    volunteer = models.BooleanField(default=True)
    coordinator = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    innovator = models.BooleanField(default=False)
    active = models.BooleanField(default=False)


    def __str__(self):
        return f'{self.user.username} Profile'

    # def save(self, *args, **kwargs):
    #     super(Profile, self).save(*args, **kwargs)
    #     img = Image.open(self.image.path)
    #
    #     if img.height > 300 or img.width > 300:
    #         output_size = (262, 330)
    #         img.thumbnail(output_size)
    #         img.save(self.image.path)



