from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and saves a new user with the given email and password.
        """
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.is_active = False
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        """
        Creates and saves a new superuser with the given email and password.
        """
        user = self.create_user(email, password=password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


# TODO add user ipaddress information for security
class UserProfile(AbstractUser):
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    image = models.ImageField(default='default.png', upload_to='profile_pics')
    phone_number = models.CharField(max_length=15, null=True)
    facebook = models.CharField(max_length=100, null=True, default="#")
    instagram = models.CharField(max_length=100, null=True, default="#")
    twitter = models.CharField(max_length=100, null=True, default="#")
    state = models.CharField(max_length=30, null=True)
    country = models.CharField(max_length=30, null=True)
    short_bio = models.CharField(
        max_length=100, null=False, default='replace with a short introduction about yourself')
    reason_joined = models.TextField(
        null=False, default='The burden to help the needy has never been more than now')
    volunteer = models.BooleanField(default=True)
    coordinator = models.BooleanField(default=False)
    date_joined = models.DateTimeField(
        auto_now_add=True, verbose_name="date_joined", null=True)
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name="date_updated", null=True)
    innovator = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    objects = UserManager()

    def __str__(self):
        return self.username

    def get_full_name(self):
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()
