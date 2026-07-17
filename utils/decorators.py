from django.http import HttpResponseBadRequest


def ajax_required(func):
    def wrap(request, *args, **kwargs):
        if request.headers.get('x-requested-with') != 'XMLHttpRequest':
            return HttpResponseBadRequest()
        return func(request, *args, **kwargs)

    wrap.__doc__ = func.__doc__
    wrap.__name__ = func.__name__
    return wrap
