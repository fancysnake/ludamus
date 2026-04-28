"""Shared mixins, request type, and helpers for panel views."""

from __future__ import annotations

from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.http import HttpRequest
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from ludamus.gates.web.django.glimpse_kit import (
    RequireAccess,
    ScopedView,
    ShortCircuitError,
)
from ludamus.gates.web.django.responses import ErrorWithMessageRedirect
from ludamus.mills import PanelService, is_proposal_active
from ludamus.pacts import DependencyInjectorProtocol, NotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

    from ludamus.pacts import (
        AreaDTO,
        AuthenticatedRequestContext,
        EventDTO,
        FacilitatorDTO,
        PersonalDataFieldDTO,
        ProposalCategoryDTO,
        SessionDTO,
        SessionFieldDTO,
        SpaceDTO,
        TimeSlotDTO,
        TrackDTO,
        VenueDTO,
    )


class PanelRequest(HttpRequest):
    """Request type for panel views with UoW and context."""

    context: AuthenticatedRequestContext
    di: DependencyInjectorProtocol


class PanelAccessMixin(RequireAccess):
    """Require login + sphere-manager status to access the panel."""

    request: PanelRequest
    denied_redirect_url = "web:index"
    denied_message = gettext_lazy(
        "You don't have permission to access the backoffice panel."
    )

    def has_access(self) -> bool:
        ctx = self.request.context
        return self.request.di.uow.spheres.is_manager(
            ctx.current_sphere_id, ctx.current_user_slug
        )


# --- pearl-string scoping -----------------------------------------------------


def _str_kwarg(kwargs: dict[str, object], *keys: str) -> str:
    """Return the first kwarg whose value is a string, by key order.

    Returns:
        The first string value found.

    Raises:
        KeyError: When none of ``keys`` resolves to a string.
    """
    for key in keys:
        value = kwargs.get(key)
        if isinstance(value, str):
            return value
    raise KeyError(keys[0])


def _int_kwarg(kwargs: dict[str, object], key: str) -> int:
    """Return a typed integer URL kwarg (Django converts ``<int:…>`` for us).

    Returns:
        The integer value of ``kwargs[key]``.

    Raises:
        KeyError: When ``kwargs[key]`` is missing or not an integer.
    """
    value = kwargs.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise KeyError(key)


class PanelEventView(PanelAccessMixin, ScopedView):
    """Pearl 1: an event in the current sphere, named ``self.event``."""

    request: PanelRequest
    event: EventDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.event = self.request.di.uow.events.read_by_slug(
                _str_kwarg(kwargs, "slug", "event_slug"),
                self.request.context.current_sphere_id,
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request, _("Event not found."), "panel:index"
                )
            ) from exc


class PanelTrackView(PanelEventView):
    """Pearl 2: a track inside the resolved event, named ``self.track``."""

    track: TrackDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.track = self.request.di.uow.tracks.read_by_slug(
                self.event.pk, _str_kwarg(kwargs, "track_slug")
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request,
                    _("Track not found."),
                    "panel:tracks",
                    slug=self.event.slug,
                )
            ) from exc


class PanelVenueView(PanelEventView):
    """Pearl 2: a venue inside the resolved event, named ``self.venue``."""

    venue: VenueDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.venue = self.request.di.uow.venues.read_by_slug(
                self.event.pk, _str_kwarg(kwargs, "venue_slug")
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request,
                    _("Venue not found."),
                    "panel:venues",
                    slug=self.event.slug,
                )
            ) from exc


class PanelAreaView(PanelVenueView):
    """Pearl 3: an area inside the resolved venue, named ``self.area``."""

    area: AreaDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.area = self.request.di.uow.areas.read_by_slug(
                self.venue.pk, _str_kwarg(kwargs, "area_slug")
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request,
                    _("Area not found."),
                    "panel:venue-detail",
                    slug=self.event.slug,
                    venue_slug=self.venue.slug,
                )
            ) from exc


class PanelSpaceView(PanelAreaView):
    """Pearl 4: a space inside the resolved area, named ``self.space``."""

    space: SpaceDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.space = self.request.di.uow.spaces.read_by_slug(
                self.area.pk, _str_kwarg(kwargs, "space_slug")
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request,
                    _("Space not found."),
                    "panel:area-detail",
                    slug=self.event.slug,
                    venue_slug=self.venue.slug,
                    area_slug=self.area.slug,
                )
            ) from exc


class PanelTimeSlotView(PanelEventView):
    """Pearl 2: a time slot in the resolved event, named ``self.time_slot``."""

    time_slot: TimeSlotDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.time_slot = self.request.di.uow.time_slots.read_by_event(
                self.event.pk, _int_kwarg(kwargs, "pk")
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request,
                    _("Time slot not found."),
                    "panel:time-slots",
                    slug=self.event.slug,
                )
            ) from exc


class PanelPersonalDataFieldView(PanelEventView):
    """Pearl 2: a personal data field in the resolved event, named ``self.field``."""

    field: PersonalDataFieldDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.field = self.request.di.uow.personal_data_fields.read_by_slug(
                self.event.pk, _str_kwarg(kwargs, "field_slug")
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request,
                    _("Personal data field not found."),
                    "panel:personal-data-fields",
                    slug=self.event.slug,
                )
            ) from exc


class PanelSessionFieldView(PanelEventView):
    """Pearl 2: a session field in the resolved event, named ``self.field``."""

    field: SessionFieldDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.field = self.request.di.uow.session_fields.read_by_slug(
                self.event.pk, _str_kwarg(kwargs, "field_slug")
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request,
                    _("Session field not found."),
                    "panel:session-fields",
                    slug=self.event.slug,
                )
            ) from exc


class PanelCFPCategoryView(PanelEventView):
    """Pearl 2: a CFP category in the resolved event, named ``self.category``."""

    category: ProposalCategoryDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.category = self.request.di.uow.proposal_categories.read_by_slug(
                self.event.pk, _str_kwarg(kwargs, "category_slug")
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request,
                    _("Session type not found."),
                    "panel:cfp",
                    slug=self.event.slug,
                )
            ) from exc


class PanelProposalView(PanelEventView):
    """Pearl 2: a proposal in the resolved event, named ``self.proposal``."""

    proposal: SessionDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        proposal_id = _int_kwarg(kwargs, "proposal_id")
        uow = self.request.di.uow
        try:
            self.proposal = uow.sessions.read(proposal_id)
        except NotFoundError as exc:
            raise ShortCircuitError(self._not_found()) from exc
        # Cross-event access guard
        session_event = uow.sessions.read_event(proposal_id)
        if session_event.pk != self.event.pk:
            raise ShortCircuitError(self._not_found())

    def _not_found(self) -> ErrorWithMessageRedirect:
        return ErrorWithMessageRedirect(
            self.request,
            _("Proposal not found."),
            "panel:proposals",
            slug=self.event.slug,
        )


class PanelFacilitatorView(PanelEventView):
    """Pearl 2: a facilitator in the resolved event, named ``self.facilitator``."""

    facilitator: FacilitatorDTO

    def bind(self, **kwargs: object) -> None:
        super().bind(**kwargs)
        try:
            self.facilitator = self.request.di.uow.facilitators.read_by_event_and_slug(
                self.event.pk, _str_kwarg(kwargs, "facilitator_slug")
            )
        except NotFoundError as exc:
            raise ShortCircuitError(
                ErrorWithMessageRedirect(
                    self.request,
                    _("Facilitator not found."),
                    "panel:facilitators",
                    slug=self.event.slug,
                )
            ) from exc


# --- shared chrome and helpers -----------------------------------------------


def panel_chrome(request: PanelRequest, event: EventDTO) -> dict[str, Any]:
    """Return the breadcrumb/sidebar context every panel page needs.

    Returns:
        A mapping with ``events``, ``current_event``, ``is_proposal_active``
        and ``stats`` keys, ready to merge into a template context.
    """
    sphere_id = request.context.current_sphere_id
    panel_service = PanelService(request.di.uow)
    return {
        "events": request.di.uow.events.list_by_sphere(sphere_id),
        "current_event": event,
        "is_proposal_active": is_proposal_active(event),
        "stats": panel_service.get_event_stats(event.pk).model_dump(),
    }


def track_filter_context(
    request: PanelRequest, event_pk: int
) -> tuple[list[Any], set[int], int | None]:
    """Return track filter context tuple for the track switcher.

    Auto-selects a single managed track when the ``track`` GET param is absent.

    Returns:
        Tuple of (sorted_tracks, managed_pks, filter_track_pk).
    """
    all_tracks = request.di.uow.tracks.list_by_event(event_pk)
    managed_tracks = request.di.uow.tracks.list_by_manager(
        request.context.current_user_id, event_pk=event_pk
    )
    managed_pks = {t.pk for t in managed_tracks}

    track_param = request.GET.get("track", "").strip()
    if "track" not in request.GET and len(managed_tracks) == 1:
        filter_track_pk: int | None = managed_tracks[0].pk
    elif track_param.isdigit():
        filter_track_pk = int(track_param)
    else:
        filter_track_pk = None

    sorted_tracks = sorted(all_tracks, key=lambda t: (t.pk not in managed_pks, t.name))
    return sorted_tracks, managed_pks, filter_track_pk


# --- transitional: kept while modules migrate --------------------------------


class EventContextMixin:
    """Mixin providing common event context for unmigrated panel views.

    Retained while migration to ``PanelEventView`` proceeds. New code should
    prefer ``PanelEventView`` (and friends) plus ``panel_chrome``.
    """

    request: PanelRequest

    def get_event_context(self, slug: str) -> tuple[dict[str, Any], EventDTO | None]:
        sphere_id = self.request.context.current_sphere_id
        events = self.request.di.uow.events.list_by_sphere(sphere_id)

        try:
            current_event = self.request.di.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return {}, None

        panel_service = PanelService(self.request.di.uow)
        stats = panel_service.get_event_stats(current_event.pk)

        context: dict[str, Any] = {
            "events": events,
            "current_event": current_event,
            "is_proposal_active": is_proposal_active(current_event),
            "stats": stats.model_dump(),
        }

        return context, current_event

    def get_track_filter_context(
        self, event_pk: int
    ) -> tuple[list[Any], set[int], int | None]:
        return track_filter_context(self.request, event_pk)


def settings_tab_urls(slug: str) -> dict[str, str]:
    return {
        "general": reverse("panel:event-settings", kwargs={"slug": slug}),
        "proposals": reverse("panel:event-proposal-settings", kwargs={"slug": slug}),
        "display": reverse("panel:event-display-settings", kwargs={"slug": slug}),
    }


def cfp_tab_urls(slug: str) -> dict[str, str]:
    return {
        "types": reverse("panel:cfp", kwargs={"slug": slug}),
        "host": reverse("panel:personal-data-fields", kwargs={"slug": slug}),
        "session": reverse("panel:session-fields", kwargs={"slug": slug}),
        "time_slots": reverse("panel:time-slots", kwargs={"slug": slug}),
    }


def make_unique_slug(
    name: str, default: str, check_exists: Callable[[str], bool]
) -> str:
    base_slug = slugify(name) or default
    slug = base_slug
    for _attempt in range(4):
        if not check_exists(slug):
            break
        slug = f"{base_slug}-{token_urlsafe(3)}"
    return slug
