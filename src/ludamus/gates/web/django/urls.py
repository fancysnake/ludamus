"""URL configuration for gates/web/django views."""

from django.urls import path

from . import panel

app_name = "panel"  # pylint: disable=invalid-name

urlpatterns = [
    path("", panel.PanelIndexRedirectView.as_view(), name="index"),
    path("event/<slug:slug>/", panel.EventIndexPageView.as_view(), name="event-index"),
    path(
        "event/<slug:slug>/settings/",
        panel.EventSettingsPageView.as_view(),
        name="event-settings",
    ),
]
