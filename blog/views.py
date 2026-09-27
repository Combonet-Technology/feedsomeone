import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import (LoginRequiredMixin,
                                        PermissionRequiredMixin,
                                        UserPassesTestMixin)
from django.contrib.postgres.search import (SearchQuery, SearchRank,
                                            SearchVector)
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Case, Count, F, Q, When
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DeleteView, ListView, UpdateView
from taggit.models import Tag

from blog.forms import ArticleForm, CommentForm, EmailShareForm, SearchForm
from blog.models import Article, Categories
from blog.seo import build_article_meta
# Get an instance of a logger
from ext_libs.email_service import send_email
from utils.views import custom_paginator, get_actual_template

logger = logging.getLogger(__name__)


# Post Page Fxn recreated into a class
class ArticleListView(ListView):
    model = Article
    context_object_name = 'objects'
    ordering = ['-date_created']
    paginate_by = 3
    template_name = 'blog/article_list.html'
    tag = None
    category = None

    def get_queryset(self):
        queryset = Article.published.all()
        if self.kwargs.get('tag'):
            self.tag = get_object_or_404(Tag, slug=self.kwargs.get('tag'))
            queryset = queryset.filter(
                Q(published_revision__tags=self.tag)
                | Q(published_revision__legacy_metadata_unverified=True, tags=self.tag)
            )
        if self.kwargs.get('category'):
            self.category = self.kwargs.get('category')
            queryset = queryset.filter(
                Q(published_revision__categories__title=self.category)
                | Q(published_revision__legacy_metadata_unverified=True,
                    category__title=self.category)
            )
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = self.tag
        context['current_category'] = self.category
        if self.category == 'Briefings':
            context['page_title'] = 'OEF News Briefings'
            context['page_heading'] = 'OEF News Briefings'
        elif self.category == 'Articles':
            context['page_title'] = 'OEF Articles'
            context['page_heading'] = 'OEF Articles'
        context['posts'] = self.object_list
        context['recent_posts'] = self.object_list.order_by('-date_created')[:8]
        return context

    def get_template_names(self):
        template_names = super().get_template_names()
        return get_actual_template(self, 'blog/article_ajax.html') + template_names

    def paginate_queryset(self, queryset, page_size):
        return custom_paginator(self.request, page_size, queryset)


def legacy_article_filter(request, value):
    """Redirect the former ambiguous filter URL to its canonical route."""
    if Categories.objects.filter(title=value).exists():
        return redirect('article:articles-by-category', category=value, permanent=True)
    return redirect('article:articles-by-slug', tag=value, permanent=True)


class UserArticleListView(LoginRequiredMixin, ListView):
    model = Article
    template_name = 'blog/article_list.html'
    context_object_name = 'objects'
    paginate_by = 3

    def get_queryset(self):
        user = get_object_or_404(get_user_model(), username=self.kwargs.get('username'))
        can_view_private = (
            self.request.user == user
            or self.request.user.is_superuser
            or self.request.user.has_perm('blog.review_article')
        )
        manager = Article.objects if can_view_private else Article.published
        if can_view_private:
            manager = manager.filter(article_author=user)
        else:
            manager = manager.filter(
                Q(published_revision__authored_by=user)
                | Q(published_revision__legacy_metadata_unverified=True,
                    article_author=user)
                | Q(published_revision__isnull=True, article_author=user)
            )
        return manager.filter(is_deleted=False).order_by('-date_created')


def get_similar_articles(article, limit=3):
    article_tags_ids = article.public_tags.values_list('id', flat=True)
    similar_articles = Article.published.filter(
        Q(published_revision__tags__in=article_tags_ids)
        | Q(published_revision__legacy_metadata_unverified=True,
            tags__in=article_tags_ids),
    ).exclude(id=article.id)
    return similar_articles.annotate(
        same_tags=Count('published_revision__tags'),
    ).order_by('-same_tags', '-publish_date')[:limit]


def article_detail(request, year, month, day, slug):
    template_name = 'blog/article_detail.html'
    article = get_object_or_404(
        Article.published,
        Q(published_revision__slug=slug)
        | Q(published_revision__legacy_metadata_unverified=True, article_slug=slug)
        | Q(published_revision__isnull=True, article_slug=slug),
        publish_date__year=year,
        publish_date__month=month,
        publish_date__day=day,
    )
    comments = article.comments.filter(active=True)
    similar_articles = get_similar_articles(article)
    posted_comment = None
    if request.method == 'POST':
        comment = CommentForm(request.POST)
        if comment.is_valid():
            new_comment = comment.save(commit=False)
            new_comment.post = article
            new_comment.save()
            if new_comment.id:
                messages.info(
                    request, 'Your comment has been posted and is awaiting moderation')
            else:
                messages.error(
                    request, 'Your comment was not posted, try again later')
            return redirect(article.get_absolute_url())
        else:
            logger.error(msg=str(comment.errors))
        messages.error(request, 'Form not fully filled, please retry.')
        return redirect(article.get_absolute_url())
    else:
        # comment_form = CommentForm()
        return render(request, template_name, {
            'article': article,
            'article_meta': build_article_meta(request, article),
            'comments': comments,
            'new_comment': posted_comment,
            'similar': similar_articles,
        })


def search_article(request):
    form = SearchForm()
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    query = request.GET.get('query')
    results = []
    page = request.GET.get('page')
    context = {'form': form,
               'page': page,
               'query': query}
    if query:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']

            def public_author_field(field):
                return Case(
                    When(published_revision__legacy_metadata_unverified=True,
                         then=F(f'article_author__{field}')),
                    default=F(f'published_revision__authored_by__{field}'),
                )

            search_vector = \
                SearchVector('published_revision__title', weight='A') + \
                SearchVector('published_revision__excerpt', weight='C') + \
                SearchVector('published_revision__content', weight='C') + \
                SearchVector(public_author_field('username'), weight='D') + \
                SearchVector(public_author_field('first_name'), weight='B') + \
                SearchVector(public_author_field('last_name'), weight='B')
            search_query = SearchQuery(query)
            results = Article.published.annotate(
                search=search_vector, rank=SearchRank(search_vector, search_query)
            ).filter(rank__gte=0.2).order_by('-rank')
        paginator = Paginator(results, 2)
        try:
            results = paginator.page(page)
        except PageNotAnInteger:
            results = paginator.page(1)
        except EmptyPage:
            if is_ajax:
                return HttpResponse('')
            results = paginator.page(paginator.num_pages)
        if is_ajax:
            context['objects'] = results
            context['query'] = query
            context['pager'] = False
            return render(request, 'blog/search_result_ajax.html', context)
    context['objects'] = results
    return render(request, 'blog/search_page.html', context)


@login_required
@permission_required('blog.add_article', raise_exception=True)
def create_article(request):
    """Preserve old bookmarks while keeping all authoring inside Django admin."""
    return redirect('admin:blog_article_add')


class UpdateArticleView(LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    permission_required = 'blog.change_article'
    template_name = 'blog/article_form.html'
    slug_url_kwarg = 'slug'
    slug_field = 'article_slug'

    def form_valid(self, form):
        form.instance.article_author = self.request.user
        return super().form_valid(form)

    def get(self, request, *args, **kwargs):
        return redirect('admin:blog_article_change', object_id=self.get_object().pk)

    def post(self, request, *args, **kwargs):
        return redirect('admin:blog_article_change', object_id=self.get_object().pk)

    def test_func(self):
        post = self.get_object()
        if self.request.user == post.article_author and not post.pending_revision_id:
            return True
        return False

    def get_success_url(self):
        article = self.get_object()
        slug = article.article_slug
        date = article.publish_date

        if article.is_published:
            return reverse('article:article_detail', kwargs={'year': date.year,
                                                             'month': date.month,
                                                             'day': date.day,
                                                             'slug': slug})
        return reverse('article:article-by-user', kwargs={'username': self.request.user.username})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_to_perform'] = "update"
        return context


class ArticleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Article
    template_name = 'blog/article_confirm_delete.html'
    context_object_name = 'post'
    slug_field = 'article_slug'

    def test_func(self):
        post = self.get_object()
        if self.request.user == post.article_author:
            return True
        return False

    def form_valid(self, form):
        return self._soft_delete()

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self._soft_delete()

    def _soft_delete(self):
        self.object.is_deleted = True
        self.object.save(update_fields=('is_deleted', 'date_updated'))
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('article:all-articles')


# Create your views here.
@login_required()
def all_post(request):
    post = Article.objects.all()
    return render(request, 'all-post.html', {'post': post})


# Create your views here.
@login_required()
def single_post(request):
    return render(request, 'article_detail.html')


# Create your views here.
def about(request):
    return render(request, 'about.html')


# remove if field later for uuid from calling function
# add option to share pot on FB, Twitter and IG
def post_share(request, slug, medium=None):
    post = get_object_or_404(
        Article.published,
        Q(published_revision__slug=slug)
        | Q(published_revision__legacy_metadata_unverified=True, article_slug=slug)
        | Q(published_revision__isnull=True, article_slug=slug),
    )
    sent = False
    if request.method == 'POST':
        form = EmailShareForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cd['name']} recommends you read {post.public_title}"
            message = f"Read {post.public_title} at {post_url}\n\n {cd['name']}\'s comments: {cd['comments']}"
            sent = send_email(destination=cd['to'], subject=subject, content=message, plain=True)
    else:
        form = EmailShareForm()

    return render(request, 'blog/share.html', {'post': post, 'form': form, 'sent': sent})
