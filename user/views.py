from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, DetailView
from .forms import UserRegistration, UserUpdateForm, ProfileUpdateForm
from django.contrib.auth.decorators import login_required
from .models import Profile
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
    if request.method == 'POST':
        user_update_form = UserUpdateForm(request.POST, instance=request.user)
        profile_update_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if user_update_form.is_valid() and profile_update_form.is_valid():
            user_update_form.save()
            profile_update_form.save()
            messages.success(request, f'Account for {request.user} updated Successfully!')
            return redirect('profile')
    else:
        user_update_form = UserUpdateForm(instance=request.user)
        profile_update_form = ProfileUpdateForm(instance=request.user.profile)
        is_profile = Profile.objects.filter(user_id=request.user.id).first()
    context = {
        'user_update_form': user_update_form,
        'profile_update_form': profile_update_form,
	'profile': is_profile,
    }
    return render(request, 'profile.html', context)
    pass
    # auth.logout(request)user_update_form = UserUpdateForm()
    #     profile_update_form = ProfileUpdateForm()
    # return redirect('/')


# @csrf_exempt
def register(request):
    # return HttpResponse('THIS IS THE REGISTER PAGE')
    if request.method == 'POST':
        form = UserRegistration(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account for {username} Created Successfully!')
            return redirect('login')
        else:
            messages.error(request, 'INVALID USER INPUTS')
            return render(request, 'register.html', {'forms': form})
    else:
        form = UserRegistration()
        return render(request, 'register.html', {'forms': form})


class VolunteerListView(ListView):
    model = Profile
    context_object_name = 'volunteers'
#    ordering = ['?']
    paginate_by = 8

    def get_queryset(self):
        return Profile.objects.exclude(active=False).order_by('date_joined')


class VolunteerDetailView(DetailView):
    model = Profile
    context_object_name = 'voulunteer'
