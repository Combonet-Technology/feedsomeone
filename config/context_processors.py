from .public_links import get_oef_social_links


def oef_social_links(request):
    return {'oef_social_links': get_oef_social_links()}
