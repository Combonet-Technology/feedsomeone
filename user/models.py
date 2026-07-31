import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from utils.enums import EthnicityEnum, ReligionEnum, StateEnum
from utils.forms import clean_email


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

    def create_superuser(self, email, password, *args, **kwargs):
        """
        Creates and saves a new superuser with the given email and password.
        """
        user = self.create_user(email=email, password=password)
        user.is_staff = True
        user.is_active = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


# TODO add user ipaddress information for security
class UserProfile(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    email = models.EmailField(unique=True, max_length=50, blank=True, null=True)
    username = models.CharField(unique=True, max_length=30, blank=True, null=True)
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    date_joined = models.DateTimeField(
        auto_now_add=True, verbose_name="date_joined", null=True)
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name="date_updated", null=True)
    is_active = models.BooleanField(default=False)  # set to true after email verification
    is_staff = models.BooleanField(default=False)
    objects = CustomUserManager()
    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email

    def get_full_name(self):
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()

    def save(self, *args, **kwargs):
        if not clean_email(str(self.email)):
            raise ValidationError("Invalid email")
        super().save(*args, **kwargs)


class VolunteerManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_verified=True, user__is_superuser=False).order_by('user__date_joined')


class Volunteer(models.Model):
    uuid = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    user = models.OneToOneField(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='volunteer')
    state_of_residence = models.CharField(_('select state'), max_length=30, null=True, blank=True,
                                          choices=[(tag.name, tag.value) for tag in StateEnum])
    ethnicity = models.CharField(max_length=30, null=True, blank=True,
                                 choices=[(tag.name, tag.value) for tag in EthnicityEnum])
    religion = models.CharField(max_length=30, null=True, blank=True,
                                choices=[(tag.name, tag.value) for tag in ReligionEnum])
    profession = models.CharField(max_length=255, null=True, blank=True)
    short_bio = models.CharField(max_length=255, null=True, blank=True)
    facebook = models.CharField(max_length=255, null=True, blank=True)
    instagram = models.CharField(max_length=255, null=True, blank=True)
    twitter = models.CharField(max_length=255, null=True, blank=True)
    image = models.ImageField(default='default.png', upload_to='profile_pics')
    phone_number = models.CharField(max_length=15, null=True)
    is_verified = models.BooleanField(default=False)
    objects = VolunteerManager()

    def __str__(self):
        return self.user.email + "'s profile"


class TeamMember(models.Model):
    ENGAGEMENT_TYPE_CHOICES = (
        ('volunteer', 'Volunteer'),
        ('internship', 'Intern'),
        ('contract', 'Contractor'),
        ('staff', 'Employee'),
        ('trustee', 'Trustee'),
    )
    STATUS_CHOICES = (
        ('invited', 'Invited'),
        ('onboarding', 'Onboarding'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('offboarded', 'Offboarded'),
    )

    user = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='team_membership',
    )
    source_application = models.OneToOneField(
        'opportunities.VacancyApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_member',
    )
    role_title = models.CharField(max_length=255)
    engagement_type = models.CharField(
        max_length=20,
        choices=ENGAGEMENT_TYPE_CHOICES,
        default='volunteer',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='invited')
    start_date = models.DateField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True, editable=False)
    access_granted_at = models.DateTimeField(null=True, blank=True, editable=False)
    access_granted_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='team_access_grants',
    )
    access_revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    access_revoked_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='team_access_revocations',
    )
    invitation_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    invitation_message_id = models.CharField(max_length=255, blank=True, editable=False)
    invitation_error = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('user__first_name', 'user__last_name', 'user__email')

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.email} - {self.role_title}'


class Lead(models.Model):
    """mark lead as converted based on user actions and create entry
     for them in donor or volunteers as the case may be"""
    options = (('Facebook', 'Facebook'),
               ('Google', 'Google'),
               ('Youtube', 'Youtube'),
               ('Twitter', 'Twitter'),
               ('Linkedin', 'Linkedin'),
               ('Website', 'Website'),
               ('Other', 'Other'))
    stages = (('Volunteer', 'Volunteer'),
              ('Donor', 'Donor'),
              ('Subscriber', 'Subscriber'),
              ('New', 'New'))
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    email = models.CharField(unique=True, null=False, blank=False, max_length=255)
    source = models.CharField(max_length=50, choices=options, null=True, blank=True, default='Website')
    stage = models.CharField(max_length=50, choices=stages, null=True, blank=True, default='New')
    converted = models.BooleanField(default=False, blank=False, null=False)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    date_updated = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f'{self.stage} {self.email} from {self.source}'

    def save(self, *args, **kwargs):
        if not clean_email(str(self.email)):
            raise ValidationError("Invalid email")
        super().save(*args, **kwargs)
