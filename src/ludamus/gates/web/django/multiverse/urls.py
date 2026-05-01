"""URL patterns for the multiverse subdomain."""

from django.urls import include, path

app_name = "multiverse"  # pylint: disable=invalid-name

urlpatterns = [
    path(
        "panel/",
        include("ludamus.gates.web.django.multiverse.panel.urls", namespace="panel"),
    )
]
