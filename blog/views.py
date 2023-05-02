import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DeleteView, ListView, UpdateView

from blog.forms import ArticleForm, CommentForm, EmailShareForm
from blog.models import Article, Categories

# Get an instance of a logger
logger = logging.getLogger(__name__)


# Post Page Fxn recreated into a class
class ArticleListView(ListView):
    model = Article
    context_object_name = 'articles'
    ordering = ['-date_created']
    paginate_by = 3
    template_name = 'blog/article_list.html'

    def get_queryset(self):
        return Article.objects.filter(is_published=True)

    def get_context_data(self, **kwargs):
        category_set = []
        context = super().get_context_data(**kwargs)
        context['posts'] = self.get_queryset()
        context['recent_posts'] = self.get_queryset().order_by("-date_created")[:8]
        categories = self.get_queryset().filter(category__isnull=False).values('category').annotate(
            ct=Count('category')).order_by(
            '-ct')[:10]
        if categories is not None:
            dist_cat = (list(categories))
            for item in dist_cat:
                category = Categories.objects.filter(
                    id=item['category']).values().first()
                category['ct'] = item['ct']
                category_set.append(category)
            context['category_set'] = category_set
        return context


class UserArticleListView(LoginRequiredMixin, ListView):
    model = Article
    template_name = 'blog/posts-by-user.html'
    context_object_name = 'post'
    paginate_by = 2

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs.get('username'))
        return Article.objects.filter(article_author=user).order_by('-date_created')


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


def article_detail(request, year, month, day, slug):
    template_name = 'blog/article_detail.html'
    article = get_object_or_404(Article, article_slug=slug,
                                publish_date__year=year,
                                publish_date__month=month,
                                publish_date__day=day)
    comments = article.comments.filter(active=True)
    posted_comment = None
    # Comment posted
    if request.method == 'POST':
        comment = CommentForm(request.POST)
        if comment.is_valid():
            cleaned_comment = comment.cleaned_data
            cleaned_comment.save(commit=False)
            cleaned_comment.post = article
            # Save the comment to the database
            cleaned_comment.save()
            # return redirect(f'/{post.id}')
            if cleaned_comment.pk:
                messages.info(
                    request, 'Your comment has been posted and is awaiting moderation')
            else:
                messages.error(
                    request, 'Your comment was not posted, try again later')
            return HttpResponseRedirect(request.headers.get('referer'))
        messages.error(request, 'Form not fully filled, please retry.')
        return HttpResponseRedirect(request.headers.get('referer'))
    else:
        # comment_form = CommentForm()
        return render(request, template_name, {
            'article': article,
            'comments': comments,
            'new_comment': posted_comment,
            'tags': 2,
        })


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
    form = None
    if request.method == 'POST':
        pass
        form = ArticleForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.save(commit=False)
            data.article_author = request.user
            data.save()
            return redirect('all-articles')
        # return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        errors = form.errors
        print(errors)
        logger.error(errors)
    article_form = form if form else ArticleForm()
    context = {
        'form': article_form,
        'action_to_perform': "create new"
    }
    return render(request, template_name, context)


class UpdateArticleView(UserPassesTestMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'blog/article_form.html'

    def form_valid(self, form):
        form.instance.article_author = self.request.user
        return super().form_valid(form)

    def test_func(self):
        post = self.get_object()
        if self.request.user == post.article_author:
            return True
        return False

    def get_success_url(self):
        slug = self.get_object().article_slug
        return reverse('article-detail', kwargs={'pk': self.kwargs["pk"], 'slug': slug})

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
    # return HttpResponse('WELCOME TO POST PAGE')
    post = Article.objects.all()
    return render(request, 'all-post.html', {'post': post})


# Create your views here.
@login_required()
def single_post(request):
    # return HttpResponse('WELCOME TO SINGLE POST')
    return render(request, 'article_detail.html')


# Create your views here.
def about(request):
    # return HttpResponse('WELCOME TO ABOUT/HOME PAGE')
    return render(request, 'about.html')


def post_share(request, post_id):
    post = get_object_or_404(Article, id=post_id)
    sent = False
    if request.method == 'POST':
        form = EmailShareForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute(post.get_absolute_url())
            subject = f"{cd['name']} recommends you read {post.title}"
            message = f"Read {post.title} at {post_url}\n\n {cd['name']}\'s comments: {cd['comments']}"
            send_mail(subject, message, 'info@oluwafemiebenezerfoundation.org', [cd['to']])
            sent = True
    else:
        form = EmailShareForm()

    return render(request, 'blog/share.html', {'post': post, 'form': form, 'sent': sent})
