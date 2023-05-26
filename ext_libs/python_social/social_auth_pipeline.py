from user.models import UserProfile, Volunteer


def create_volunteer(user=None, *args, **kwargs):
    if user:
        if hasattr(user, 'volunteer'):
            return {"is_new": False}

    volunteer, _ = Volunteer.objects.get_or_create(user=user)
    return {'user': user}


def merge_user(user=None, *args, **kwargs):
    email = kwargs['response'].get('email') or kwargs['response'].get('emailAddress')
    if email:
        try:
            existing = UserProfile.objects.get(email=email)
            return {"is_new": False, "user": existing}
        except UserProfile.DoesNotExist:
            return {"is_new": True}
