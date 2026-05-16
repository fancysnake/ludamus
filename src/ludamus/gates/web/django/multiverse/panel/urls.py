"""URL patterns for the multiverse panel bounded context."""

from django.urls import path

from ludamus.gates.web.django.multiverse.panel.views import credentials, sphere_settings

app_name = "panel"  # pylint: disable=invalid-name

urlpatterns = [
    path("", sphere_settings.SphereSettingsPageView.as_view(), name="sphere-settings"),
    path("credentials/", credentials.CredentialsPageView.as_view(), name="credentials"),
    path(
        "credentials/create/",
        credentials.CredentialCreatePageView.as_view(),
        name="credential-create",
    ),
    path(
        "credentials/<int:pk>/edit/",
        credentials.CredentialEditPageView.as_view(),
        name="credential-edit",
    ),
    path(
        "credentials/<int:pk>/do/delete/",
        credentials.CredentialDeletePageView.as_view(),
        name="credential-delete",
    ),
]
