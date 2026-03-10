from django.urls import URLPattern, path

from . import views

urlpatterns: list[URLPattern] = [
    path(
        "event/<str:event_slug>/session/propose",
        views.ProposeSessionPageView.as_view(),
        name="session-propose",
    )
]
