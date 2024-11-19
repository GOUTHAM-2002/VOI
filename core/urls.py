from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import signup_view, CustomLoginView

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
]
