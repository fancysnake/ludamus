"""Import/Export panel views: CRUD for per-event API connections."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.chronology.panel.forms import EventAPIConnectionForm
from ludamus.gates.web.django.chronology.panel.views.base import (
    EventContextMixin,
    PanelAccessMixin,
    PanelRequest,
)
from ludamus.pacts import NotFoundError
from ludamus.pacts.multiverse import ConnectionKind, CredentialAuthError

if TYPE_CHECKING:
    from django.http import HttpResponse

    from ludamus.pacts import EventDTO
    from ludamus.pacts.chronology import (
        EventAPIConnectionDTO,
        EventAPIConnectionWriteDict,
    )


_ACTIVE_NAV = "import-export"
_LIST_URL_NAME = "panel:import-export"
_CREATE_TEMPLATE = "panel/import-export/create.html"
_EDIT_TEMPLATE = "panel/import-export/edit.html"


def _connection_choices(
    request: PanelRequest, kind: ConnectionKind
) -> list[tuple[int, str]]:
    sphere_id = request.context.current_sphere_id
    return [
        (c.pk, c.display_name)
        for c in request.services.connections.list_for_sphere(sphere_id)
        if c.kind == kind
    ]


def _class_choices(
    request: PanelRequest, kind: ConnectionKind
) -> list[tuple[str, str]]:
    return [(cls.name, cls.name) for cls in request.services.shop_api.for_kind(kind)]


def _form_choices(
    request: PanelRequest,
) -> tuple[list[tuple[int, str]], list[tuple[str, str]]]:
    # Today only TICKET_API has a registered implementation; widen here
    # when ingest/export classes land.
    kind = ConnectionKind.TICKET_API
    return _connection_choices(request, kind), _class_choices(request, kind)


def _form_data_to_write_dict(
    form: EventAPIConnectionForm,
) -> EventAPIConnectionWriteDict:
    return {
        "connection_id": int(form.cleaned_data["connection"]),
        "class_name": form.cleaned_data["class_name"],
        "config": {
            "url": form.cleaned_data["url"],
            "count_json_path": form.cleaned_data["count_json_path"],
        },
    }


def _row_not_found_redirect(request: PanelRequest, slug: str) -> HttpResponse:
    messages.error(request, _("API connection not found."))
    return redirect(_LIST_URL_NAME, slug=slug)


def _resolve_event(
    view: EventContextMixin, slug: str
) -> tuple[dict[str, Any], EventDTO] | None:
    context, current_event = view.get_event_context(slug)
    if current_event is None:
        return None
    return context, current_event


def _try_load_row(
    request: PanelRequest, event_pk: int, pk: int
) -> EventAPIConnectionDTO | None:
    try:
        return request.services.event_api_connections.get(event_pk, pk)
    except NotFoundError:
        return None


class ImportExportPageView(PanelAccessMixin, EventContextMixin, View):
    """List the per-event external API connections."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        if (resolved := _resolve_event(self, slug)) is None:
            return redirect("panel:index")
        context, current_event = resolved
        sphere_id = self.request.context.current_sphere_id
        items = self.request.services.event_api_connections.list_for_event(
            sphere_id, current_event.pk
        )
        context["active_nav"] = _ACTIVE_NAV
        context["items"] = items
        return TemplateResponse(self.request, "panel/import-export/list.html", context)


class ImportExportCreatePageView(PanelAccessMixin, EventContextMixin, View):
    """Create a per-event external API connection."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        if (resolved := _resolve_event(self, slug)) is None:
            return redirect("panel:index")
        context, _current_event = resolved
        connection_choices, class_choices = _form_choices(self.request)
        context["active_nav"] = _ACTIVE_NAV
        context["form"] = EventAPIConnectionForm(
            connection_choices=connection_choices, class_choices=class_choices
        )
        return TemplateResponse(self.request, _CREATE_TEMPLATE, context)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        if (resolved := _resolve_event(self, slug)) is None:
            return redirect("panel:index")
        context, current_event = resolved

        connection_choices, class_choices = _form_choices(self.request)
        form = EventAPIConnectionForm(
            self.request.POST,
            connection_choices=connection_choices,
            class_choices=class_choices,
        )
        if not form.is_valid():
            context["active_nav"] = _ACTIVE_NAV
            context["form"] = form
            return TemplateResponse(self.request, _CREATE_TEMPLATE, context)

        sphere_id = self.request.context.current_sphere_id
        try:
            self.request.services.event_api_connections.create(
                sphere_id, current_event.pk, _form_data_to_write_dict(form)
            )
        except CredentialAuthError as exc:
            form.add_error(None, exc.detail)
            context["active_nav"] = _ACTIVE_NAV
            context["form"] = form
            return TemplateResponse(self.request, _CREATE_TEMPLATE, context)

        messages.success(self.request, _("API connection created successfully."))
        return redirect(_LIST_URL_NAME, slug=slug)


class ImportExportEditPageView(PanelAccessMixin, EventContextMixin, View):
    """Edit a per-event external API connection."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        if (resolved := _resolve_event(self, slug)) is None:
            return redirect("panel:index")
        context, current_event = resolved
        if (row := _try_load_row(self.request, current_event.pk, pk)) is None:
            return _row_not_found_redirect(self.request, slug)

        connection_choices, class_choices = _form_choices(self.request)
        config = row.config
        context["active_nav"] = _ACTIVE_NAV
        context["row"] = row
        context["form"] = EventAPIConnectionForm(
            initial={
                "connection": str(row.connection_id),
                "class_name": row.class_name,
                "url": config.get("url", ""),
                "count_json_path": config.get("count_json_path", ""),
            },
            connection_choices=connection_choices,
            class_choices=class_choices,
        )
        return TemplateResponse(self.request, _EDIT_TEMPLATE, context)

    def post(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        if (resolved := _resolve_event(self, slug)) is None:
            return redirect("panel:index")
        context, current_event = resolved
        if (row := _try_load_row(self.request, current_event.pk, pk)) is None:
            return _row_not_found_redirect(self.request, slug)

        connection_choices, class_choices = _form_choices(self.request)
        form = EventAPIConnectionForm(
            self.request.POST,
            connection_choices=connection_choices,
            class_choices=class_choices,
        )
        if not form.is_valid():
            context["active_nav"] = _ACTIVE_NAV
            context["row"] = row
            context["form"] = form
            return TemplateResponse(self.request, _EDIT_TEMPLATE, context)

        sphere_id = self.request.context.current_sphere_id
        try:
            self.request.services.event_api_connections.update(
                sphere_id, current_event.pk, pk, _form_data_to_write_dict(form)
            )
        except CredentialAuthError as exc:
            form.add_error(None, exc.detail)
            context["active_nav"] = _ACTIVE_NAV
            context["row"] = row
            context["form"] = form
            return TemplateResponse(self.request, _EDIT_TEMPLATE, context)

        messages.success(self.request, _("API connection updated successfully."))
        return redirect(_LIST_URL_NAME, slug=slug)


class ImportExportDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a per-event external API connection (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        if (resolved := _resolve_event(self, slug)) is None:
            return redirect("panel:index")
        _ctx, current_event = resolved
        try:
            self.request.services.event_api_connections.delete(current_event.pk, pk)
        except NotFoundError:
            return _row_not_found_redirect(self.request, slug)
        messages.success(self.request, _("API connection deleted successfully."))
        return redirect(_LIST_URL_NAME, slug=slug)
