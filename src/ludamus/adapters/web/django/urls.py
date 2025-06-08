# 📁 webappexample/urls.py -----

from django.urls import path

from . import views

app_name = "web_main"

urlpatterns = [
    path("", views.index, name="index"),
    path("profile/login", views.login, name="login"),
    path("profile/logout", views.logout, name="logout"),
    path("profile/callback", views.callback, name="callback"),
    path("profile/edit", views.UsernameView.as_view(), name="edit"),
    path("profile/redirect", views.redirect_view, name="redirect"),
]
