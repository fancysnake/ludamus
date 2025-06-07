# 📁 webappexample/urls.py -----

from django.urls import path

from . import views

app_name = "web_main"

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login, name="login"),
    path("logout", views.logout, name="logout"),
    path("callback", views.callback, name="callback"),
    path("username", views.UsernameView.as_view(), name="username"),
    path("redirect", views.redirect_view, name="redirect"),
]
