import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and saves a new user with the given email and password.
        """
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.is_active = True
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        """
        Creates and saves a new superuser with the given email and password.
        """
        user = self.create_user(email=email, password=password)
        user.is_staff = True
        user.is_active = True
        user.is_verified = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

    def get_queryset(self):
        return super().get_queryset() \
            .filter(is_verified=True)


# TODO add user ipaddress information for security
class UserProfile(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    email = models.EmailField(unique=True, max_length=30, blank=True, null=True)
    username = models.CharField(unique=True, max_length=30, blank=True, null=True)
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    image = models.ImageField(default='default.png', upload_to='profile_pics')
    phone_number = models.CharField(max_length=15, null=True)
    state = models.CharField(max_length=30, null=True)
    country = models.CharField(max_length=30, null=True)
    short_bio = models.CharField(max_length=255, null=True, blank=True)
    date_joined = models.DateTimeField(
        auto_now_add=True, verbose_name="date_joined", null=True)
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name="date_updated", null=True)
    is_active = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def get_full_name(self):
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()
