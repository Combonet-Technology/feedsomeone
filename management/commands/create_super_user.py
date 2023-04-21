import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Creates a superuser.'

    def handle(self, *args, **options):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username=os.getenv('SUPER_USERNAME'),
                password=os.getenv('SUPER_USER_PASSWORD')
            )
        print('Superuser has been created.')
