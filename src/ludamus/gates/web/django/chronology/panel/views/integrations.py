"""Event integration CRUD + check views (event panel)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol

from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.chronology.panel.forms import (
    EventIntegrationForm,
    integration_signature,
)
from ludamus.gates.web.django.chronology.panel.views.base import (
    EventContextMixin,
    PanelAccessMixin,
    PanelRequest,
)
from ludamus.pacts import NotFoundError
from ludamus.pacts.chronology import (
    EventIntegrationCreateData,
    EventIntegrationUpdateData,
    IntegrationCheckRequest,
    IntegrationImplementationId,
    IntegrationKind,
)

if TYPE_CHECKING:
    from django.http import HttpResponse

    from ludamus.pacts import EventDTO
    from ludamus.pacts.chronology import EventIntegrationDTO


class _PanelViewLike(Protocol):
    request: PanelRequest

    def get_event_context(
        self, slug: str
    ) -> tuple[dict[str, Any], EventDTO | None]: ...


def _parse_kind(raw: str) -> IntegrationKind | None:
    try:
        return IntegrationKind(raw)
    except ValueError:
        return None


def _form_kwargs(request: PanelRequest, kind: IntegrationKind) -> dict[str, Any]:
    sphere_id = request.context.current_sphere_id
    return {
        "kind": kind,
        "implementations": request.services.event_integrations.list_implementations(
            kind
        ),
        "connections": request.services.connections.list_for_sphere(sphere_id),
    }


def _load_integration(
    view: _PanelViewLike, slug: str, pk: int
) -> (
    tuple[dict[str, Any], EventDTO, EventIntegrationDTO]
    | tuple[None, None, HttpResponse]
):
    # On miss returns (None, None, redirect_response) — caller returns the
    # third element as-is; otherwise (context, event, integration).
    context, current_event = view.get_event_context(slug)
    if current_event is None:
        return None, None, redirect("panel:index")
    try:
        integration = view.request.services.event_integrations.get(current_event.pk, pk)
    except NotFoundError:
        messages.error(view.request, _("Integration not found."))
        return None, None, redirect("panel:event-index", slug=slug)
    return context, current_event, integration


class IntegrationCreatePageView(PanelAccessMixin, EventContextMixin, View):
    """Create a new event integration of a given kind."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, kind: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")
        if (kind_enum := _parse_kind(kind)) is None:
            return HttpResponseBadRequest("Unknown integration kind")
        form = EventIntegrationForm(**_form_kwargs(self.request, kind_enum))
        context["active_nav"] = "integrations"
        context["form"] = form
        context["kind"] = kind_enum
        return TemplateResponse(
            self.request, "chronology/panel/integrations/create.html", context
        )

    def post(self, _request: PanelRequest, slug: str, kind: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")
        if (kind_enum := _parse_kind(kind)) is None:
            return HttpResponseBadRequest("Unknown integration kind")

        form = EventIntegrationForm(
            self.request.POST, **_form_kwargs(self.request, kind_enum)
        )
        if not form.is_valid():
            context["active_nav"] = "integrations"
            context["form"] = form
            context["kind"] = kind_enum
            return TemplateResponse(
                self.request, "chronology/panel/integrations/create.html", context
            )

        sphere_id = self.request.context.current_sphere_id
        self.request.services.event_integrations.create(
            sphere_id=sphere_id,
            event_id=current_event.pk,
            data=EventIntegrationCreateData(
                kind=kind_enum,
                implementation=form.cleaned_data["implementation"],
                connection_id=int(form.cleaned_data["connection"]),
                display_name=form.cleaned_data["display_name"],
                config_json=form.cleaned_data["config_json"],
            ),
        )
        messages.success(self.request, _("Integration created."))
        return redirect("panel:event-index", slug=slug)


class IntegrationEditPageView(PanelAccessMixin, EventContextMixin, View):
    """Edit an existing event integration."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        loaded = _load_integration(self, slug, pk)
        if loaded[1] is None:
            return loaded[2]
        context, _current_event, integration = loaded

        form = EventIntegrationForm(
            initial={
                "display_name": integration.display_name,
                "implementation": integration.implementation,
                "connection": str(integration.connection_id),
                "config_json": json.dumps(integration.config_json, indent=2),
            },
            initial_connection_id=integration.connection_id,
            initial_config_json=integration.config_json,
            **_form_kwargs(self.request, integration.kind),
        )
        # Lock implementation on edit — kind+impl pair is structural.
        form.fields["implementation"].disabled = True
        context["active_nav"] = "integrations"
        context["form"] = form
        context["integration"] = integration
        return TemplateResponse(
            self.request, "chronology/panel/integrations/edit.html", context
        )

    def post(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        loaded = _load_integration(self, slug, pk)
        if loaded[1] is None:
            return loaded[2]
        context, current_event, integration = loaded

        form = EventIntegrationForm(
            self.request.POST,
            initial={"implementation": integration.implementation},
            initial_connection_id=integration.connection_id,
            initial_config_json=integration.config_json,
            **_form_kwargs(self.request, integration.kind),
        )
        form.fields["implementation"].disabled = True
        if not form.is_valid():
            context["active_nav"] = "integrations"
            context["form"] = form
            context["integration"] = integration
            return TemplateResponse(
                self.request, "chronology/panel/integrations/edit.html", context
            )

        sphere_id = self.request.context.current_sphere_id
        self.request.services.event_integrations.update(
            sphere_id=sphere_id,
            event_id=current_event.pk,
            pk=pk,
            data=EventIntegrationUpdateData(
                display_name=form.cleaned_data["display_name"],
                connection_id=int(form.cleaned_data["connection"]),
                config_json=form.cleaned_data["config_json"],
            ),
        )
        messages.success(self.request, _("Integration updated."))
        return redirect("panel:event-index", slug=slug)


class IntegrationDeletePageView(PanelAccessMixin, EventContextMixin, View):
    """Confirm-and-delete page for an event integration."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        loaded = _load_integration(self, slug, pk)
        if loaded[1] is None:
            return loaded[2]
        context, _current_event, integration = loaded
        context["active_nav"] = "integrations"
        context["integration"] = integration
        return TemplateResponse(
            self.request, "chronology/panel/integrations/delete.html", context
        )

    def post(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        loaded = _load_integration(self, slug, pk)
        if loaded[1] is None:
            return loaded[2]
        _ctx, current_event, _integration = loaded
        self.request.services.event_integrations.delete(current_event.pk, pk)
        messages.success(self.request, _("Integration deleted."))
        return redirect("panel:event-index", slug=slug)


class IntegrationCheckActionView(PanelAccessMixin, EventContextMixin, View):
    """POST-only HTMX endpoint that runs `Check integration`.

    Returns the outcome partial as the response body.
    """

    request: PanelRequest

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        _ctx, current_event = self.get_event_context(slug)
        if current_event is None:
            return HttpResponseBadRequest("Unknown event")

        implementation_raw = (self.request.POST.get("implementation") or "").strip()
        connection_raw = (self.request.POST.get("connection") or "").strip()
        config_raw = self.request.POST.get("config_json") or "{}"

        if not implementation_raw or not connection_raw:
            return TemplateResponse(
                self.request,
                "chronology/panel/integrations/_check_result.html",
                {
                    "outcome": "input_missing",
                    "hint": _(
                        "Pick an implementation and a connection before "
                        "running the check."
                    ),
                    "signature": "",
                },
            )

        try:
            implementation = IntegrationImplementationId(implementation_raw)
        except ValueError:
            return TemplateResponse(
                self.request,
                "chronology/panel/integrations/_check_result.html",
                {
                    "outcome": "not_found",
                    "hint": (
                        _("Unknown implementation: %(id)s") % {"id": implementation_raw}
                    ),
                    "signature": "",
                },
            )

        try:
            connection_id = int(connection_raw)
        except ValueError:
            return HttpResponseBadRequest("Bad connection id")

        try:
            config_json = json.loads(config_raw)
        except json.JSONDecodeError as exc:
            return TemplateResponse(
                self.request,
                "chronology/panel/integrations/_check_result.html",
                {"outcome": "invalid_json", "hint": str(exc), "signature": ""},
            )
        if not isinstance(config_json, dict):
            return TemplateResponse(
                self.request,
                "chronology/panel/integrations/_check_result.html",
                {
                    "outcome": "invalid_json",
                    "hint": _("Configuration must be a JSON object."),
                    "signature": "",
                },
            )

        sphere_id = self.request.context.current_sphere_id
        result = self.request.services.event_integrations.check(
            IntegrationCheckRequest(
                sphere_id=sphere_id,
                implementation=implementation,
                connection_id=connection_id,
                config_json=config_json,
            )
        )
        signature = (
            integration_signature(connection_id, config_json)
            if str(result.outcome) == "ok"
            else ""
        )
        return TemplateResponse(
            self.request,
            "chronology/panel/integrations/_check_result.html",
            {
                "outcome": str(result.outcome),
                "hint": result.hint,
                "signature": signature,
            },
        )
