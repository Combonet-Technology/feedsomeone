import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from user.management.services import CreateSuperUserService

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates a superuser.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.superuser_email = os.getenv('SUPER_USER_EMAIL')
        self.superuser_password = os.getenv('SUPER_USER_PASSWORD')

    def handle(self, *args, **options):
        CreateSuperUserService.create_superuser(self.superuser_email, self.superuser_password)
