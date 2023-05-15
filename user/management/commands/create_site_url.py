import os

from django.core.management.base import BaseCommand

from user.management.services import SiteService


class Command(BaseCommand):
    help = 'Creates site object for current or new user.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site_name = os.getenv('SITE_NAME')
        self.site_domain = os.getenv('SITE_DOMAIN')

    def handle(self, *args, **options):
        SiteService.add_site(self.site_name, self.site_domain)
