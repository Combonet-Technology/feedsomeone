import os

from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class SiteService:
    @staticmethod
    def add_site(name, domain):
        try:
            site, created = Site.objects.get_or_create(name=name, domain=domain)
            if not created:
                print(f'Site {name} with domain {domain} already exist')
        except Exception as e:
            print(f"Error creating site: {str(e)}")
        else:
            print(f'Site {name} with domain {domain} created successfully')


class Command(BaseCommand):
    help = 'Creates site object for current or new user.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site_name = os.getenv('SITE_NAME')
        self.site_domain = os.getenv('SITE_DOMAIN')

    def handle(self, *args, **options):
        SiteService.add_site(self.site_name, self.site_domain)
