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
    path("event/<slug:slug>/venues/", panel.VenuesPageView.as_view(), name="venues"),
    path(
        "event/<slug:slug>/venues/structure/",
        panel.VenuesStructurePageView.as_view(),
        name="venues-structure",
    ),
    path(
        "event/<slug:slug>/venues/create/",
        panel.VenueCreatePageView.as_view(),
        name="venue-create",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/edit/",
        panel.VenueEditPageView.as_view(),
        name="venue-edit",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/do/delete",
        panel.VenueDeleteActionView.as_view(),
        name="venue-delete",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/do/duplicate",
        panel.VenueDuplicatePageView.as_view(),
        name="venue-duplicate",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/do/copy",
        panel.VenueCopyPageView.as_view(),
        name="venue-copy",
    ),
    path(
        "event/<slug:slug>/venues/do/reorder",
        panel.VenueReorderActionView.as_view(),
        name="venue-reorder",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/",
        panel.VenueDetailPageView.as_view(),
        name="venue-detail",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/areas/create/",
        panel.AreaCreatePageView.as_view(),
        name="area-create",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/areas/<str:area_slug>/edit/",
        panel.AreaEditPageView.as_view(),
        name="area-edit",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/areas/<str:area_slug>/do/delete",
        panel.AreaDeleteActionView.as_view(),
        name="area-delete",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/areas/do/reorder",
        panel.AreaReorderActionView.as_view(),
        name="area-reorder",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/areas/<str:area_slug>/",
        panel.AreaDetailPageView.as_view(),
        name="area-detail",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/areas/<str:area_slug>/spaces/create/",
        panel.SpaceCreatePageView.as_view(),
        name="space-create",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/areas/<str:area_slug>/spaces/"
        "<str:space_slug>/edit/",
        panel.SpaceEditPageView.as_view(),
        name="space-edit",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/areas/<str:area_slug>/spaces/"
        "<str:space_slug>/do/delete",
        panel.SpaceDeleteActionView.as_view(),
        name="space-delete",
    ),
    path(
        "event/<slug:slug>/venues/<str:venue_slug>/areas/<str:area_slug>/spaces/do/reorder",
        panel.SpaceReorderActionView.as_view(),
        name="space-reorder",
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
