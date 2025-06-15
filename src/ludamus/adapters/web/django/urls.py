# 📁 webappexample/urls.py -----

from django.urls import path

from . import views

app_name = "web_main"  # pylint: disable=invalid-name

urlpatterns = [
    path("", views.index, name="index"),
    path("profile/callback", views.callback, name="callback"),
    path("profile/edit", views.EditProfileView.as_view(), name="edit"),
    path("profile/login", views.login, name="login"),
    path("profile/logout", views.logout, name="logout"),
    path("profile/redirect", views.redirect_view, name="redirect"),
    path("profile/connected", views.ConnectedView.as_view(), name="connected"),
    path(
        "profile/connected/<str:slug>",
        views.EditConnectedView.as_view(),
        name="connected-details",
    ),
    path(
        "profile/connected/<str:slug>/delete",
        views.DeleteConnectedView.as_view(),
        name="connected-delete",
    ),
]
