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
    path("event/<slug:slug>/cfp/", panel.CFPPageView.as_view(), name="cfp"),
    path(
        "event/<slug:slug>/cfp/create/",
        panel.CFPCreatePageView.as_view(),
        name="cfp-create",
    ),
    path(
        "event/<slug:slug>/cfp/personal-data/",
        panel.PersonalDataFieldsPageView.as_view(),
        name="personal-data-fields",
    ),
    path(
        "event/<slug:slug>/cfp/personal-data/create/",
        panel.PersonalDataFieldCreatePageView.as_view(),
        name="personal-data-field-create",
    ),
    path(
        "event/<slug:slug>/cfp/personal-data/<str:field_slug>/edit/",
        panel.PersonalDataFieldEditPageView.as_view(),
        name="personal-data-field-edit",
    ),
    path(
        "event/<slug:slug>/cfp/personal-data/<str:field_slug>/do/delete",
        panel.PersonalDataFieldDeleteActionView.as_view(),
        name="personal-data-field-delete",
    ),
    path(
        "event/<slug:event_slug>/cfp/<str:category_slug>/",
        panel.CFPEditPageView.as_view(),
        name="cfp-edit",
    ),
    path(
        "event/<slug:event_slug>/cfp/<str:category_slug>/do/delete",
        panel.CFPDeleteActionView.as_view(),
        name="cfp-delete",
    ),
]
