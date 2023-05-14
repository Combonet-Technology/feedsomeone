import os

from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Creates a superuser.'

    def handle(self, *args, **options):
        site_name = os.getenv('SITE_NAME')
        site_domain = os.getenv('SITE_DOMAIN')
        Site.objects.filter(name='example.com').delete()
        try:
            Site.objects.create(name=site_name, domain=site_domain)
        except Exception as e:
            print(f'Site creation failed with error {str(e)}')
        else:
            print('Site url has been created.')
