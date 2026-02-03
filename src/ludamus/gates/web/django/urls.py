"""URL configuration for gates/web/django views."""

from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from ludamus.gates.web.django import panel

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse
    from django.urls import URLPattern, URLResolver


handler404 = (  # pylint: disable=invalid-name
    "ludamus.adapters.web.django.error_views.custom_404"
)
handler500 = (  # pylint: disable=invalid-name
    "ludamus.adapters.web.django.error_views.custom_500"
)


panel_urlpatterns = [
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
        "event/<slug:slug>/cfp/session-fields/",
        panel.SessionFieldsPageView.as_view(),
        name="session-fields",
    ),
    path(
        "event/<slug:slug>/cfp/session-fields/create/",
        panel.SessionFieldCreatePageView.as_view(),
        name="session-field-create",
    ),
    path(
        "event/<slug:slug>/cfp/session-fields/<str:field_slug>/edit/",
        panel.SessionFieldEditPageView.as_view(),
        name="session-field-edit",
    ),
    path(
        "event/<slug:slug>/cfp/session-fields/<str:field_slug>/do/delete",
        panel.SessionFieldDeleteActionView.as_view(),
        name="session-field-delete",
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


urlpatterns: list[URLResolver | URLPattern] = [
    path("", include("ludamus.adapters.web.django.urls", namespace="web")),
    path("panel/", include((panel_urlpatterns, "panel"), namespace="panel")),
    path("admin/", admin.site.urls),
    path("page/", include("django.contrib.flatpages.urls")),
]


if settings.DEBUG:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]

    # Debug URLs to test error pages
    def _trigger_500(_: HttpRequest) -> HttpResponse:
        raise ValueError

    from ludamus.adapters.web.django.error_views import (  # pylint: disable=ungrouped-imports
        custom_404,
        custom_500,
    )

    urlpatterns += [
        path("404/", lambda r: custom_404(r, None)),
        path("500/", custom_500),
        path("500-real/", _trigger_500),
    ]

    if "debug_toolbar" in settings.INSTALLED_APPS:
        from debug_toolbar.toolbar import debug_toolbar_urls

        urlpatterns += debug_toolbar_urls()
