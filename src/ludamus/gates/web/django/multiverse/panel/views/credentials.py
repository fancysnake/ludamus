"""Credential CRUD views for the sphere panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.multiverse.access import (
    MultiverseRequest,
    SphereAccessMixin,
)
from ludamus.gates.web.django.multiverse.panel.forms import CredentialForm
from ludamus.gates.web.django.multiverse.panel.views.base import sphere_panel_context
from ludamus.pacts import NotFoundError, RedirectError

if TYPE_CHECKING:
    from django.http import HttpResponse

    from ludamus.pacts.multiverse import CredentialWriteDict


def _credential_not_found() -> RedirectError:
    return RedirectError(
        reverse("multiverse:panel:credentials"), error=_("Credential not found.")
    )


class CredentialsPageView(SphereAccessMixin, View):
    """List API credentials for the current sphere."""

    request: MultiverseRequest

    def get(self, _request: MultiverseRequest) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        credentials = self.request.services.credentials.list_for_sphere(sphere_id)
        return TemplateResponse(
            self.request,
            "multiverse/panel/credentials/list.html",
            {
                **sphere_panel_context(self.request, active_tab="credentials"),
                "credentials": credentials,
            },
        )


class CredentialCreatePageView(SphereAccessMixin, View):
    """Create a new API credential."""

    request: MultiverseRequest

    def get(self, _request: MultiverseRequest) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "multiverse/panel/credentials/create.html",
            {
                **sphere_panel_context(self.request, active_tab="credentials"),
                "form": CredentialForm(is_create=True),
            },
        )

    def post(self, _request: MultiverseRequest) -> HttpResponse:
        form = CredentialForm(self.request.POST, is_create=True)
        if not form.is_valid():
            return TemplateResponse(
                self.request,
                "multiverse/panel/credentials/create.html",
                {
                    **sphere_panel_context(self.request, active_tab="credentials"),
                    "form": form,
                },
            )

        sphere_id = self.request.context.current_sphere_id
        data: CredentialWriteDict = {"display_name": form.cleaned_data["display_name"]}
        plaintext = form.cleaned_data["credentials"].encode("utf-8")
        self.request.services.credentials.create(sphere_id, data, plaintext)
        messages.success(self.request, _("Credential created successfully."))
        return redirect("multiverse:panel:credentials")


class CredentialEditPageView(SphereAccessMixin, View):
    """Edit an existing API credential."""

    request: MultiverseRequest

    def get(self, _request: MultiverseRequest, pk: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            credential = self.request.services.credentials.get(sphere_id, pk)
        except NotFoundError:
            raise _credential_not_found() from None

        form = CredentialForm(initial={"display_name": credential.display_name})
        return TemplateResponse(
            self.request,
            "multiverse/panel/credentials/edit.html",
            {
                **sphere_panel_context(self.request, active_tab="credentials"),
                "form": form,
                "credential": credential,
            },
        )

    def post(self, _request: MultiverseRequest, pk: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            credential = self.request.services.credentials.get(sphere_id, pk)
        except NotFoundError:
            raise _credential_not_found() from None

        form = CredentialForm(self.request.POST)
        if not form.is_valid():
            return TemplateResponse(
                self.request,
                "multiverse/panel/credentials/edit.html",
                {
                    **sphere_panel_context(self.request, active_tab="credentials"),
                    "form": form,
                    "credential": credential,
                },
            )

        data: CredentialWriteDict = {"display_name": form.cleaned_data["display_name"]}
        if form.cleaned_data["replace_credentials"]:
            plaintext = form.cleaned_data["credentials"].encode("utf-8")
            self.request.services.credentials.update(sphere_id, pk, data, plaintext)
        else:
            self.request.services.credentials.update(sphere_id, pk, data)
        messages.success(self.request, _("Credential updated successfully."))
        return redirect("multiverse:panel:credentials")


class CredentialDeletePageView(SphereAccessMixin, View):
    """Confirm-and-delete page for a credential."""

    request: MultiverseRequest

    def get(self, _request: MultiverseRequest, pk: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            credential = self.request.services.credentials.get(sphere_id, pk)
        except NotFoundError:
            raise _credential_not_found() from None

        return TemplateResponse(
            self.request,
            "multiverse/panel/credentials/delete.html",
            {
                **sphere_panel_context(self.request, active_tab="credentials"),
                "credential": credential,
            },
        )

    def post(self, _request: MultiverseRequest, pk: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            self.request.services.credentials.delete(sphere_id, pk)
        except NotFoundError:
            raise _credential_not_found() from None

        messages.success(self.request, _("Credential deleted successfully."))
        return redirect("multiverse:panel:credentials")
