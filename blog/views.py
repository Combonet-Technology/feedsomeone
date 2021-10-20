import logging
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import render, get_object_or_404, redirect

# from blog.forms import CommentForm
from django.urls import reverse
from django_summernote.fields import SummernoteTextFormField

from blog.forms import ArticleForm
# from blog.forms import CategoryForm, ArticleForm
from blog.models import Article, Comments, Categories
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User

# Get an instance of a logger
logger = logging.getLogger(__name__)


# Post Page Fxn recreated into a class
class ArticleListView(LoginRequiredMixin, ListView):
    model = Article
    context_object_name = 'posts'
    ordering = ['-date_created']
    paginate_by = 3
    template_name = 'blog/article_list.html'

    def get_context_data(self, **kwargs):
        category_set = []
        context = super(ArticleListView, self).get_context_data(**kwargs)
        context['posts'] = Article.objects.all()
        context['recent_posts'] = Article.objects.order_by("-date_created")[:8]
        categories = Article.objects.filter(category__isnull=False).values('category').annotate(ct=Count('category')).order_by(
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
        return Article.objects.filter(post_author=user).order_by('-date_created')


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


def article_detail(request, pk, slug):
    template_name = 'blog/article_detail.html'
    # post = get_object_or_404(Post, pk=pk)
    post = get_object_or_404(Article, pk=pk, article_slug=slug)
    comments = post.comments.filter(active=True)
    posted_comment = None
    # Comment posted
    if request.method == 'POST':
        # exit('tired')
        comment_form = request.POST
        name = comment_form.get('name')
        email = comment_form.get('email')
        website = comment_form.get('website')
        comment = comment_form.get('comment')
        while name != '' and email != '' and website != '' and comment != '':
            # Create Comment object but don't save to database yet
            new_comment = Comments.objects.create(
                name=name, email=email, website=website, body=comment, post_id=post.id)
            new_comment.save()
            # posted_comment = new_comment.save(commit=False)
            # Assign the current post to the comment
            # posted_comment.post = post
            # Save the comment to the database
            # posted_comment.save()
            # return redirect(f'/{post.id}')
            if new_comment.pk:
                messages.info(
                    request, 'Your comment has been posted and is awaiting moderation')
            else:
                messages.error(
                    request, 'Your comment was not posted, try again later')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        messages.error(request, 'Form not fully filled, please retry.')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    else:
        # comment_form = CommentForm()
        return render(request, template_name, {
            'post': post,
            'comments': comments,
            'new_comment': posted_comment,
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


class UpdateArticleView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
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


class ArticleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
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
