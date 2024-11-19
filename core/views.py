from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView
from .forms import UserSignupForm, UserLoginForm

# Signup View
def signup_view(request):
    if request.method == 'POST':
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')  # Redirect to a homepage or dashboard
    else:
        form = UserSignupForm()
    return render(request, 'core/signup.html', {'form': form})

# Login View
class CustomLoginView(LoginView):
    form_class = UserLoginForm
    template_name = 'core/login.html'
