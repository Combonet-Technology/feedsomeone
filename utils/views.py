from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse


def custom_paginator(request, page_size, queryset):
    paginator = Paginator(queryset, page_size)
    page = request.GET.get('page')
    try:
        results = paginator.page(page)
    except PageNotAnInteger:
        results = paginator.page(1)
    except EmptyPage:
        if request.is_ajax():
            return HttpResponse('')
        results = paginator.page(paginator.num_pages)
    is_paginated = len(results) > 0
    return paginator, page, results, is_paginated


def get_actual_template(view_obj, extra_template):
    if view_obj.request.is_ajax():
        return [extra_template]
    return []