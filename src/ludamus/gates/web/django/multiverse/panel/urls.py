"""URL patterns for the multiverse panel bounded context."""

from django.urls import path

from ludamus.gates.web.django.multiverse.panel.views import connections

app_name = "panel"  # pylint: disable=invalid-name

urlpatterns = [
    path("connections/", connections.ConnectionsPageView.as_view(), name="connections"),
    path(
        "connections/create/",
        connections.ConnectionCreatePageView.as_view(),
        name="connection-create",
    ),
    path(
        "connections/<int:pk>/edit/",
        connections.ConnectionEditPageView.as_view(),
        name="connection-edit",
    ),
    path(
        "connections/<int:pk>/do/delete",
        connections.ConnectionDeletePageView.as_view(),
        name="connection-delete",
    ),
]
