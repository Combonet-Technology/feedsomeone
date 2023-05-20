from social_django.models import UserSocialAuth

from user.models import Volunteer


def create_volunteer(user=None, *args, **kwargs):
    if user is None:
        user_id = kwargs['response']['id']
        user_profile = UserSocialAuth.objects.get(uid=user_id).user
        volunteer, _ = Volunteer.objects.get_or_create(user=user_profile)
        user = volunteer.user
    return {'user': user}
