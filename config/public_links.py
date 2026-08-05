from django.conf import settings


def get_oef_social_links():
    return {
        'instagram_url': settings.OEF_INSTAGRAM_URL,
        'linkedin_url': settings.OEF_LINKEDIN_URL,
        'x_url': settings.OEF_X_URL,
        'youtube_url': settings.OEF_YOUTUBE_URL,
    }
