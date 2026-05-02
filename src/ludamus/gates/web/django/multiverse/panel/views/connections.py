"""Connection CRUD views for the sphere panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.multiverse.access import (
    MultiverseRequest,
    SphereAccessMixin,
)
from ludamus.gates.web.django.multiverse.panel.forms import ConnectionForm
from ludamus.gates.web.django.multiverse.panel.views.base import sphere_panel_context
from ludamus.pacts import NotFoundError
from ludamus.pacts.multiverse import ConnectionProvider, ConnectionWriteDict

if TYPE_CHECKING:
    from django.http import HttpResponse


class ConnectionsPageView(SphereAccessMixin, View):
    """List import connections for the current sphere."""

    request: MultiverseRequest

    def get(self, _request: MultiverseRequest) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        connections = self.request.services.connections.list_for_sphere(sphere_id)
        return TemplateResponse(
            self.request,
            "multiverse/panel/connections/list.html",
            {
                **sphere_panel_context(self.request, active_tab="connections"),
                "connections": connections,
            },
        )


class ConnectionCreatePageView(SphereAccessMixin, View):
    """Create a new import connection."""

    request: MultiverseRequest

    def get(self, _request: MultiverseRequest) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "multiverse/panel/connections/create.html",
            {
                **sphere_panel_context(self.request, active_tab="connections"),
                "form": ConnectionForm(),
            },
        )

    def post(self, _request: MultiverseRequest) -> HttpResponse:
        form = ConnectionForm(self.request.POST)
        if not form.is_valid():
            return TemplateResponse(
                self.request,
                "multiverse/panel/connections/create.html",
                {
                    **sphere_panel_context(self.request, active_tab="connections"),
                    "form": form,
                },
            )

        sphere_id = self.request.context.current_sphere_id
        data: ConnectionWriteDict = {
            "service": ConnectionProvider(form.cleaned_data["service"]),
            "display_name": form.cleaned_data["display_name"],
        }
        self.request.services.connections.create(sphere_id, data)
        messages.success(self.request, _("Connection created successfully."))
        return redirect("multiverse:panel:connections")


class ConnectionEditPageView(SphereAccessMixin, View):
    """Edit an existing import connection."""

    request: MultiverseRequest

    def get(self, _request: MultiverseRequest, pk: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            connection = self.request.services.connections.get(sphere_id, pk)
        except NotFoundError:
            messages.error(self.request, _("Connection not found."))
            return redirect("multiverse:panel:connections")

        form = ConnectionForm(
            initial={
                "service": connection.service.value,
                "display_name": connection.display_name,
            }
        )
        return TemplateResponse(
            self.request,
            "multiverse/panel/connections/edit.html",
            {
                **sphere_panel_context(self.request, active_tab="connections"),
                "form": form,
                "connection": connection,
            },
        )

    def post(self, _request: MultiverseRequest, pk: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            connection = self.request.services.connections.get(sphere_id, pk)
        except NotFoundError:
            messages.error(self.request, _("Connection not found."))
            return redirect("multiverse:panel:connections")

        form = ConnectionForm(self.request.POST)
        if not form.is_valid():
            return TemplateResponse(
                self.request,
                "multiverse/panel/connections/edit.html",
                {
                    **sphere_panel_context(self.request, active_tab="connections"),
                    "form": form,
                    "connection": connection,
                },
            )

        data: ConnectionWriteDict = {
            "service": ConnectionProvider(form.cleaned_data["service"]),
            "display_name": form.cleaned_data["display_name"],
        }
        if form.cleaned_data["replace_credentials"]:
            plaintext = form.cleaned_data["credentials"].encode("utf-8")
            self.request.services.connections.test_then_update(
                sphere_id, pk, data, plaintext
            )
        else:
            self.request.services.connections.update(sphere_id, pk, data)
        messages.success(self.request, _("Connection updated successfully."))
        return redirect("multiverse:panel:connections")


class ConnectionDeletePageView(SphereAccessMixin, View):
    """Confirm-and-delete page for a connection."""

    request: MultiverseRequest

    def get(self, _request: MultiverseRequest, pk: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            connection = self.request.services.connections.get(sphere_id, pk)
        except NotFoundError:
            messages.error(self.request, _("Connection not found."))
            return redirect("multiverse:panel:connections")

        return TemplateResponse(
            self.request,
            "multiverse/panel/connections/delete.html",
            {
                **sphere_panel_context(self.request, active_tab="connections"),
                "connection": connection,
            },
        )

    def post(self, _request: MultiverseRequest, pk: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            blockers = self.request.services.connections.delete(sphere_id, pk)
        except NotFoundError:
            messages.error(self.request, _("Connection not found."))
            return redirect("multiverse:panel:connections")

        if blockers:
            messages.error(
                self.request,
                _("Cannot delete connection — used by: %(events)s.")
                % {"events": ", ".join(blockers)},
            )
            return redirect("multiverse:panel:connections")

        messages.success(self.request, _("Connection deleted successfully."))
        return redirect("multiverse:panel:connections")
