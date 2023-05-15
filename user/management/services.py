from django.contrib.sites.models import Site

from user.management.commands.create_super_user import User


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


class CreateSuperUserService:
    @staticmethod
    def create_superuser(email, password):
        try:
            User.objects.create_superuser(email=email, password=password)
        except Exception as e:
            print(f'Super user creation failed with error {str(e)}')
        else:
            print('Superuser has been created.')

    @staticmethod
    def recover_superuser_password(email, password=None):
        try:
            user = User.objects.get(email=email)
            if not password:
                password = User.objects.make_random_password()
                print(f'New password generated for superuser {email}: {password}')
            user.set_password(password)
            user.save()
            print(f'Password set for superuser {email} Successfully')
        except User.DoesNotExist:
            print(f'Superuser with email {email} does not exist')
        except Exception as e:
            print(f'Error recovering superuser password: {str(e)}')
