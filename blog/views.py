import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.postgres.search import (SearchQuery, SearchRank,
                                            SearchVector)
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DeleteView, ListView, UpdateView
from taggit.models import Tag

from blog.forms import ArticleForm, CommentForm, EmailShareForm, SearchForm
from blog.models import Article, Categories
# Get an instance of a logger
from ext_libs.sendgrid.sengrid import send_email

logger = logging.getLogger(__name__)


# Post Page Fxn recreated into a class
class ArticleListView(ListView):
    model = Article
    context_object_name = 'articles'
    ordering = ['-date_created']
    paginate_by = 3
    template_name = 'blog/article_list.html'
    tag = None
    category = None

    def get_queryset(self):
        queryset = Article.published.all()
        print(queryset)
        if self.kwargs.get('tag'):
            self.tag = get_object_or_404(Tag, slug=self.kwargs.get('tag'))
            queryset = queryset.filter(tags__in=[self.tag])
        if self.kwargs.get('category'):
            queryset = queryset.filter(category__title=self.kwargs.get('category'))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = self.tag
        context['posts'] = self.get_queryset()
        context['recent_posts'] = self.get_queryset().order_by("-date_created")[:8]
        return context


class UserArticleListView(LoginRequiredMixin, ListView):
    model = Article
    template_name = 'blog/article_list.html'
    context_object_name = 'articles'
    paginate_by = 3

    def get_queryset(self):
        user = get_object_or_404(get_user_model(), username=self.kwargs.get('username'))
        articles = Article.objects.filter(article_author=user).order_by('-date_created')
        return articles


# class ArticleDetailView(LoginRequiredMixin, DetailView):
#     model = Article, Comment
#     # template_name = 'article_detail.html'
#     # context_object_name = 'post'
#     paginate_by = 1
#
#     def get_context_data(self, **kwargs):
#          # Comment posted
#         if request.method == 'POST':
#             comment_form = CommentForm(data=request.POST)
#             if comment_form.is_valid():
#                 # Create Comment object but don't save to database yet
#                 new_comment = comment_form.save(commit=False)
#                 # Assign the current post to the comment
#                 new_comment.post = post
#                 # Save the comment to the database
#                 new_comment.save()
#         else:
#             comment_form = CommentForm()
#
#         context = super(ArticleDeleteView, self).get_context_data(**kwargs)
#         context['post'] = Article.objects.all()
#         context['comment'] = Article.comments.filter(active=True)
#         return context
#         new_comment = None


def get_similar_articles(article, limit=3):
    article_tags_ids = article.tags.values_list('id', flat=True)
    similar_articles = Article.objects.filter(tags__in=article_tags_ids).exclude(id=article.id)
    return similar_articles.annotate(same_tags=Count('tags')).order_by('-same_tags', '-publish_date')[:limit]


def article_detail(request, year, month, day, slug):
    template_name = 'blog/article_detail.html'
    article = get_object_or_404(Article, article_slug=slug,
                                publish_date__year=year,
                                publish_date__month=month,
                                publish_date__day=day)
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
            return HttpResponseRedirect(request.headers.get('referer'))
        else:
            logger.error(msg=str(comment.errors))
        messages.error(request, 'Form not fully filled, please retry.')
        return HttpResponseRedirect(request.headers.get('referer'))
    else:
        # comment_form = CommentForm()
        return render(request, template_name, {
            'article': article,
            'comments': comments,
            'new_comment': posted_comment,
            'similar': similar_articles,
        })


def search_article(request):
    form = SearchForm()
    query = None
    results = []
    page = request.GET.get('page')
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            search_vector = \
                SearchVector('article_title', weight='A') + SearchVector('article_excerpt', weight='C') + \
                SearchVector('article_content', weight='C') + SearchVector('article_author__username', weight='D') + \
                SearchVector('article_author__first_name', weight='B') + SearchVector('article_author__last_name',
                                                                                      weight='B')
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
            results = paginator.page(paginator.num_pages)

    return render(request, 'blog/search_page.html',
                  {'form': form,
                   'page': page,
                   'query': query,
                   'results': results})


# class ArticleDetailView(LoginRequiredMixin, DetailView):
#     model = Article
#     # template_name = 'article_detail.html'
#     context_object_name = 'post'


# class CreateArticleView(LoginRequiredMixin, CreateView):
#     model = ['Post', 'Category']
#     fields = ['post_title', 'post_excerpt', 'post_content', 'feature_img']
#     # success_url = ''
#
#     def form_valid(self, form):
#         form.instance.article_author = self.request.user
#         return super(CreateArticleView, self).form_valid(form)


@login_required
def create_article(request):
    template_name = 'blog/article_form.html'

    if request.method == 'POST':
        article_form = ArticleForm(request.POST, request.FILES)

        if article_form.is_valid():
            article = article_form.save(commit=False)
            print(article_form.data)
            article.article_author = request.user
            article.save()

            for category in article_form.cleaned_data['category']:
                new_category_instance, _ = Categories.objects.get_or_create(title=category)
                article.category.add(new_category_instance)

            article_form.save_m2m()
            return redirect('article:all-articles')

        article_errors = article_form.errors
        logger.error(article_errors)
    else:
        article_form = ArticleForm()

    context = {
        'form': article_form,
        'action_to_perform': "create new"
    }
    return render(request, template_name, context)


class UpdateArticleView(UserPassesTestMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'blog/article_form.html'
    slug_url_kwarg = 'slug'
    slug_field = 'article_slug'

    def form_valid(self, form):
        form.instance.article_author = self.request.user
        image_field = form.cleaned_data.get('image_field')
        if isinstance(image_field, InMemoryUploadedFile):
            form.instance.image_field.save(
                image_field.name,
                image_field,
                save=False
            )

        return super().form_valid(form)

    def test_func(self):
        post = self.get_object()
        if self.request.user == post.article_author:
            return True
        return False

    def get_success_url(self):
        article = self.get_object()
        slug = article.article_slug
        date = article.publish_date

        return reverse('article:article_detail', kwargs={'year': date.year,
                                                         'month': date.month,
                                                         'day': date.day,
                                                         'slug': slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_to_perform'] = "update"
        return context


class ArticleDeleteView(UserPassesTestMixin, DeleteView):
    model = Article
    # template_name = 'article_detail.html'
    context_object_name = 'post'
    success_url = '/'

    def test_func(self):
        post = self.get_object()
        if self.request.user == post.article_author:
            return True
        return False


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
    post = get_object_or_404(Article, article_slug=slug)
    sent = False
    if request.method == 'POST':
        form = EmailShareForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cd['name']} recommends you read {post.article_title}"
            message = f"Read {post.article_title} at {post_url}\n\n {cd['name']}\'s comments: {cd['comments']}"
            sent = send_email(settings.EMAIL_HOST_USER, [cd['to']], subject, message, plain=True)
    else:
        form = EmailShareForm()

    return render(request, 'blog/share.html', {'post': post, 'form': form, 'sent': sent})
