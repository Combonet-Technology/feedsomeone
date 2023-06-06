import logging

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist

User = get_user_model()
logger = logging.getLogger(__name__)


class SiteService:
    @staticmethod
    def add_site(name, domain):
        try:
            site, created = Site.objects.get_or_create(name=name, domain=domain)
            if not created:
                logger.info(f'Site {name} with domain {domain} already exists')
        except Exception as e:
            logger.error(f"Error creating site: {str(e)}")
        else:
            logger.info(f'Site {name} with domain {domain} created successfully')

    @staticmethod
    def remove_site(domain):
        try:
            Site.objects.filter(domain=domain).delete()
        except ObjectDoesNotExist:
            logger.warning('Non-existent domain does not exist')


class CreateSuperUserService:
    @staticmethod
    def create_superuser(email, password):
        try:
            User.objects.create_superuser(email=email, password=password)
        except Exception as e:
            logger.error(f'Super user creation failed with error {str(e)}')
        else:
            logger.info('Superuser has been created.')

    @staticmethod
    def recover_superuser_password(email, password=None):
        try:
            user = User.objects.get(email=email)
            if not password:
                password = User.objects.make_random_password()
                logger.info(f'New password generated for superuser {email}: {password}')
            user.set_password(password)
            user.save()
            logger.info(f'Password set for superuser {email} successfully')
        except User.DoesNotExist:
            logger.warning(f'Superuser with email {email} does not exist')
        except Exception as e:
            logger.error(f'Error recovering superuser password: {str(e)}')
