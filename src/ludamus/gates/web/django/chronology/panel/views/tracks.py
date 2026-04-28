"""Track views (configurable lanes spanning spaces and managers)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View
from pydantic import BaseModel, Field

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelEventView,
    PanelRequest,
    PanelTrackView,
    panel_chrome,
)
from ludamus.gates.web.django.forms import TrackForm
from ludamus.gates.web.django.responses import SuccessWithMessageRedirect
from ludamus.pacts import TrackCreateData, TrackUpdateData

if TYPE_CHECKING:
    from django.http import HttpResponse


class TrackInput(BaseModel):
    """Validated POST data for track create/edit."""

    name: str
    is_public: bool = False
    space_pks: list[int] = Field(default_factory=list)
    manager_pks: list[int] = Field(default_factory=list)


def _track_form_input(request: PanelRequest, form: TrackForm) -> TrackInput:
    return TrackInput.model_validate(
        {
            "name": form.cleaned_data["name"],
            "is_public": form.cleaned_data.get("is_public", False),
            "space_pks": request.POST.getlist("space_pks"),
            "manager_pks": request.POST.getlist("manager_pks"),
        }
    )


class TracksPageView(PanelEventView, View):
    """List tracks for an event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return TemplateResponse(
            request,
            "panel/tracks.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "tracks",
                "tracks": request.di.uow.tracks.list_by_event(self.event.pk),
            },
        )


class TrackCreatePageView(PanelEventView, View):
    """Create a new track for an event."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(TrackForm(initial={"is_public": True}), [], [])

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = TrackForm(request.POST)
        space_pks = _post_int_list(request, "space_pks")
        manager_pks = _post_int_list(request, "manager_pks")
        if not form.is_valid():
            return self._render(form, space_pks, manager_pks)

        parsed = _track_form_input(request, form)
        request.di.uow.tracks.create(
            TrackCreateData(
                event_pk=self.event.pk,
                name=parsed.name,
                is_public=parsed.is_public or True,
                space_pks=parsed.space_pks,
                manager_pks=parsed.manager_pks,
            )
        )
        return SuccessWithMessageRedirect(
            request,
            _("Track created successfully."),
            "panel:tracks",
            slug=self.event.slug,
        )

    def _render(
        self,
        form: TrackForm,
        selected_space_pks: list[int],
        selected_manager_pks: list[int],
    ) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/track-create.html",
            {
                **panel_chrome(self.request, self.event),
                **_track_choices_context(self.request, self.event.pk),
                "active_nav": "tracks",
                "form": form,
                "selected_space_pks": selected_space_pks,
                "selected_manager_pks": selected_manager_pks,
            },
        )


class TrackEditPageView(PanelTrackView, View):
    """Edit an existing track."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            TrackForm(
                initial={"name": self.track.name, "is_public": self.track.is_public}
            ),
            request.di.uow.tracks.list_space_pks(self.track.pk),
            request.di.uow.tracks.list_manager_pks(self.track.pk),
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = TrackForm(request.POST)
        space_pks = _post_int_list(request, "space_pks")
        manager_pks = _post_int_list(request, "manager_pks")
        if not form.is_valid():
            return self._render(form, space_pks, manager_pks)

        parsed = _track_form_input(request, form)
        request.di.uow.tracks.update(
            self.track.pk,
            TrackUpdateData(
                name=parsed.name,
                is_public=parsed.is_public,
                space_pks=parsed.space_pks,
                manager_pks=parsed.manager_pks,
            ),
        )
        return SuccessWithMessageRedirect(
            request,
            _("Track updated successfully."),
            "panel:tracks",
            slug=self.event.slug,
        )

    def _render(
        self,
        form: TrackForm,
        selected_space_pks: list[int],
        selected_manager_pks: list[int],
    ) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/track-edit.html",
            {
                **panel_chrome(self.request, self.event),
                **_track_choices_context(self.request, self.event.pk),
                "active_nav": "tracks",
                "track": self.track,
                "form": form,
                "selected_space_pks": selected_space_pks,
                "selected_manager_pks": selected_manager_pks,
            },
        )


class TrackDeleteActionView(PanelTrackView, View):
    """Delete a track (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        request.di.uow.tracks.delete(self.track.pk)
        return SuccessWithMessageRedirect(
            request, _("Track deleted."), "panel:tracks", slug=self.event.slug
        )


def _track_choices_context(request: PanelRequest, event_pk: int) -> dict[str, Any]:
    sphere_id = request.context.current_sphere_id
    return {
        "spaces": request.di.uow.spaces.list_by_event(event_pk),
        "managers": request.di.uow.spheres.list_managers(sphere_id),
    }


def _post_int_list(request: PanelRequest, key: str) -> list[int]:
    return [int(pk) for pk in request.POST.getlist(key) if pk.isdigit()]
