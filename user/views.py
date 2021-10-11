from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, DetailView
from .forms import UserProfileRegistration, UserProfileUpdateForm
from django.contrib.auth.decorators import login_required
from .models import UserProfile
from django.core.files.storage import default_storage


# def login(request):
#     if request.method == 'POST':
#         return HttpResponse('THIS IS THE LOGIN PAGE')
#     #     username = request.POST['username']
#     #     password = request.POST['password']
#     #
#     #     user = auth.authenticate(username=username, password=password)
#     #
#     #     if user is not None:
#     #         auth.login(request, user)
#     #         return redirect('/')
#     #
#     #     else:
#     #         messages.error(request, f'Username or Password incorrect, returned {user}')
#     #         return redirect('login')
#     #
#     else:
#         return redirect('login')


@login_required()
def profile(request):
    current_user_profile = UserProfile.objects.filter(id=request.user.id).first()
    if request.method == 'POST':
        user_update_form = UserProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if user_update_form.is_valid():  # and profile_update_form.is_valid():
            user_update_form.save()
            messages.success(request, f'Account for {request.user} updated Successfully!')
            return redirect('profile')
    else:
        user_update_form = UserProfileUpdateForm(instance=request.user)
    context = {
        'user_update_form': user_update_form,
        'user': current_user_profile,
    }
    return render(request, 'profile.html', context)
    pass
    # auth.logout(request)
    # user_update_form = UserUpdateForm()
    # profile_update_form = ProfileUpdateForm()
    # return redirect('/')


# @csrf_exempt
def register(request):
    if request.method == 'POST':
        form = UserProfileRegistration(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account for {username} Created Successfully!')
            return redirect('login')
        else:
            messages.error(request, 'INVALID USER INPUTS')
            return render(request, 'register.html', {'forms': form})
    else:
        form = UserProfileRegistration()
        return render(request, 'register.html', {'forms': form})


class VolunteerListView(ListView):
    model = UserProfile
    template_name = 'user/profile_list.html'
    context_object_name = 'volunteers'
    #    ordering = ['?']
    paginate_by = 8

    def get_queryset(self):
        return UserProfile.objects.exclude(is_active=False).order_by('date_joined')


class VolunteerDetailView(DetailView):
    model = UserProfile
    context_object_name = 'volunteer'
