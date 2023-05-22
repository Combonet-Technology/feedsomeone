from social_django.models import UserSocialAuth

from user.models import UserProfile, Volunteer


def create_volunteer(user=None, *args, **kwargs):
    if user:
        if hasattr(user, 'volunteer'):
            return {"is_new": False}

    user_id = kwargs['response']['id']
    user_profile = UserSocialAuth.objects.get(uid=user_id).user
    volunteer, _ = Volunteer.objects.get_or_create(user=user_profile)
    user = volunteer.user
    return {'user': user}


def merge_user(strategy, details, backend, user=None, *args, **kwargs):
    if user:
        return {"is_new": False}
    existing = UserProfile.objects.get(email=kwargs['response'].get('email'))
    if existing:
        return {"is_new": False, "user": existing}
