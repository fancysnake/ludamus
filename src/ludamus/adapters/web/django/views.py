import json
from collections import defaultdict
from collections.abc import Generator
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from secrets import token_urlsafe
from typing import Any
from urllib.parse import quote_plus, urlencode, urlparse

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.generic.base import ContextMixin, RedirectView, TemplateView, View
from django.views.generic.detail import DetailView, SingleObjectTemplateResponseMixin
from django.views.generic.edit import FormMixin, ProcessFormView

from ludamus.adapters.db.django.models import (
    MAX_CONNECTED_USERS,
    AgendaItem,
    EnrollmentConfig,
    Event,
    Proposal,
    ProposalCategory,
    Session,
    SessionParticipation,
    SessionParticipationStatus,
    Space,
    Tag,
    TimeSlot,
)
from ludamus.adapters.oauth import oauth
from ludamus.adapters.web.django.entities import (
    SessionData,
    SessionUserParticipationData,
)
from ludamus.links.dao import NotFoundError
from ludamus.pacts import (
    ProposalCategoryDTO,
    RootDAOProtocol,
    TagCategoryDTO,
    TagDTO,
    UserDAOProtocol,
    UserDTO,
)

from .exceptions import RedirectError
from .forms import (
    ConnectedUserForm,
    ThemeSelectionForm,
    UserForm,
    create_enrollment_form,
    create_proposal_acceptance_form,
    create_session_proposal_form,
    get_tag_data_from_form,
)

MINIMUM_ALLOWED_USER_AGE = 16
CACHE_TIMEOUT = 600  # 10 minutes


class RootDAORequest(HttpRequest):
    root_dao: RootDAOProtocol
    user_dao: UserDAOProtocol | None


class AuthorizedRootDAORequest(RootDAORequest):
    user_dao: UserDAOProtocol


class LoginRequiredPageView(TemplateView):
    template_name = "crowd/login_required.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context


class Auth0LoginActionView(View):
    @staticmethod
    def get(request: RootDAORequest) -> HttpResponse:
        """Redirect to Auth0 for authentication.

        Returns:
            HttpResponse: Redirect to Auth0 authorization endpoint.

        Raises:
            RedirectError: If the request is not from the root domain.
        """
        root_domain = request.root_dao.root_site.domain
        next_path = request.GET.get("next")
        if request.get_host() != root_domain:
            url = f'{request.scheme}://{root_domain}{reverse("web:crowd:auth0:login")}?next={next_path}'
            raise RedirectError(url)

        # Generate a secure state token
        state_token = token_urlsafe(32)

        # Store state data in cache with 10 minute timeout
        state_data = {
            "redirect_to": next_path,
            "created_at": datetime.now(UTC).isoformat(),
            "csrf_token": request.META.get("CSRF_COOKIE", ""),
        }
        cache_key = f"oauth_state:{state_token}"
        cache.set(cache_key, json.dumps(state_data), timeout=CACHE_TIMEOUT)

        return oauth.auth0.authorize_redirect(  # type: ignore [no-any-return]
            request,
            request.build_absolute_uri(reverse("web:crowd:auth0:login-callback")),
            state=state_token,
        )


class Auth0LoginCallbackActionView(RedirectView):
    request: RootDAORequest

    def get_redirect_url(self, *args: Any, **kwargs: Any) -> str | None:
        redirect_to = super().get_redirect_url(*args, **kwargs)

        # Validate state parameter
        state_token = self.request.GET.get("state")
        if not state_token:
            messages.error(
                self.request,
                _("Invalid authentication request: missing state parameter"),
            )
            return self.request.build_absolute_uri(reverse("web:index"))

        # Retrieve and validate state data
        cache_key = f"oauth_state:{state_token}"
        state_data_json = cache.get(cache_key)

        if not state_data_json:
            messages.error(
                self.request, _("Authentication session expired. Please try again.")
            )
            return self.request.build_absolute_uri(reverse("web:index"))

        # Delete state from cache immediately to prevent replay attacks
        cache.delete(cache_key)

        try:
            state_data = json.loads(state_data_json)
            redirect_to = state_data.get("redirect_to") or redirect_to or ""

            # Validate state timestamp
            created_at = datetime.fromisoformat(state_data["created_at"])
            if datetime.now(UTC) - created_at > timedelta(minutes=10):
                messages.error(
                    self.request, _("Authentication session expired. Please try again.")
                )
                return self.request.build_absolute_uri(reverse("web:index"))

        except (KeyError, ValueError):
            messages.error(self.request, _("Invalid authentication state"))
            return self.request.build_absolute_uri(reverse("web:index"))

        # Handle login/signup
        if not self.request.user_dao:
            username = self._get_username()
            auth_dao = self.request.root_dao.get_auth_dao()
            auth_dao.fetch_or_create_user(username=username, slug=slugify(username))
            # Log the user in
            django_login(
                self.request,
                auth_dao._storage.maybe_user,  # type: ignore [attr-defined] # noqa: SLF001
            )
            if self.request.session.get("anonymous_enrollment_active"):
                self.request.session.pop("anonymous_user_code", None)
                self.request.session.pop("anonymous_enrollment_active", None)
                self.request.session.pop("anonymous_event_id", None)
            messages.success(self.request, _("Welcome!"))

            # Check if profile needs completion
            if auth_dao.user.is_incomplete:
                messages.success(self.request, _("Please complete your profile."))
                if redirect_to:
                    parsed = urlparse(redirect_to)
                    return f'{parsed.scheme}://{parsed.netloc}{reverse("web:crowd:profile")}'
                return self.request.build_absolute_uri(reverse("web:crowd:profile"))

        return redirect_to or self.request.build_absolute_uri(reverse("web:index"))

    def _get_username(self) -> str:
        token = oauth.auth0.authorize_access_token(self.request)

        try:
            return f'auth0|{token["userinfo"]["sub"].encode("UTF-8")}'
        except (KeyError, TypeError):
            raise RedirectError(
                reverse("web:index"), error=_("Authentication failed")
            ) from None


class Auth0LogoutActionView(RedirectView):
    request: RootDAORequest

    def get_redirect_url(self, *args: Any, **kwargs: Any) -> str | None:
        redirect_to = super().get_redirect_url(*args, **kwargs)

        django_logout(self.request)

        last_domain = self.request.root_dao.current_site.domain
        messages.success(self.request, _("You have been successfully logged out."))

        return _auth0_logout_url(
            self.request, last_domain=last_domain, redirect_to=redirect_to
        )


def _auth0_logout_url(
    request: RootDAORequest,
    *,
    last_domain: str | None = None,
    redirect_to: str | None = None,
) -> str:
    root_domain = request.root_dao.root_site.domain
    last_domain = last_domain or root_domain
    redirect_to = redirect_to or reverse("web:index")
    return f"https://{settings.AUTH0_DOMAIN}/v2/logout?" + urlencode(
        {
            "returnTo": (
                f'{request.scheme}://{root_domain}{reverse("web:crowd:auth0:logout-redirect")}?last_domain={last_domain}&redirect_to={redirect_to}'
            ),
            "client_id": settings.AUTH0_CLIENT_ID,
        },
        quote_via=quote_plus,
    )


class Auth0LogoutRedirectActionView(RedirectView):
    request: RootDAORequest
    pattern_name = "web:index"

    def get_redirect_url(self, *args: Any, **kwargs: Any) -> str | None:
        redirect_url = super().get_redirect_url(*args, **kwargs)

        # Get the redirect_to parameter
        if redirect_to := self.request.GET.get("redirect_to"):
            # Only allow relative URLs (starting with /)
            if redirect_to.startswith("/") and not redirect_to.startswith("//"):
                redirect_url = redirect_to
            else:
                messages.warning(self.request, _("Invalid redirect URL."))

        # Handle last_domain parameter for multi-site redirects
        if last_domain := self.request.GET.get("last_domain"):
            # Validate that the domain belongs to a known site
            allowed_domains = self.request.root_dao.allowed_domains

            # Also allow subdomains of ROOT_DOMAIN if configured
            if hasattr(settings, "ROOT_DOMAIN") and (
                last_domain.endswith(f".{settings.ROOT_DOMAIN}")
                or last_domain == settings.ROOT_DOMAIN
            ):
                return f"{self.request.scheme}://{last_domain}{redirect_url}"

            # Check against explicitly allowed domains
            if last_domain in allowed_domains:
                return f"{self.request.scheme}://{last_domain}{redirect_url}"

            messages.warning(self.request, _("Invalid domain for redirect."))

        return redirect_url


class IndexPageView(TemplateView):
    request: RootDAORequest
    template_name = "index.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["events"] = list(
            Event.objects.filter(
                sphere_id=self.request.root_dao.current_sphere.pk
            ).all()
        )
        return context


class ProfilePageView(
    LoginRequiredMixin,
    SingleObjectTemplateResponseMixin,
    FormMixin,  # type: ignore [type-arg]
    ContextMixin,
    ProcessFormView,
):
    form_class = UserForm
    request: AuthorizedRootDAORequest
    success_url = reverse_lazy("web:index")
    template_name = "crowd/user/edit.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        kwargs["user"] = self.request.user_dao.user
        kwargs["object"] = self.request.user_dao.user
        return super().get_context_data(**kwargs)

    def form_valid(self, form: UserForm) -> HttpResponse:
        self.request.user_dao.update_user(form.user_data)
        messages.success(self.request, _("Profile updated successfully!"))
        return super().form_valid(form)

    def form_invalid(self, form: forms.Form) -> HttpResponse:
        messages.warning(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


class ProfileConnectedUsersPageView(
    LoginRequiredMixin,
    SingleObjectTemplateResponseMixin,
    FormMixin,  # type: ignore [type-arg]
    ContextMixin,
    ProcessFormView,
):
    form_class = ConnectedUserForm
    object: UserDTO
    request: AuthorizedRootDAORequest
    success_url = reverse_lazy("web:crowd:profile-connected-users")
    template_name = "crowd/user/connected.html"
    template_name_suffix = "_form"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        connected_users = [
            {
                "user": connected,
                "form": ConnectedUserForm(initial=connected.model_dump()),
            }
            for connected in self.request.user_dao.connected_users
        ]
        context["connected_users"] = connected_users
        context["max_connected_users"] = MAX_CONNECTED_USERS
        return context

    def form_valid(self, form: ConnectedUserForm) -> HttpResponse:
        # Check if user has reached the maximum number of connected users

        connected_count = len(self.request.user_dao.connected_users)
        if connected_count >= MAX_CONNECTED_USERS:
            messages.error(
                self.request,
                _("You can only have up to %(max)s connected users.")
                % {"max": MAX_CONNECTED_USERS},
            )
            return self.form_invalid(form)

        user_data = form.user_data
        user_data["username"] = f"connected|{token_urlsafe(50)}"
        user_data["slug"] = slugify(user_data["username"][:50])
        result = super().form_valid(form)
        self.request.user_dao.create_connected_user(user_data=user_data)
        messages.success(self.request, _("Connected user added successfully!"))
        return result

    def form_invalid(self, form: ConnectedUserForm) -> HttpResponse:
        messages.warning(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


class ProfileConnectedUserUpdateActionView(
    LoginRequiredMixin,
    SingleObjectTemplateResponseMixin,
    FormMixin,  # type: ignore [type-arg]
    ContextMixin,
    ProcessFormView,
):

    form_class = ConnectedUserForm
    request: AuthorizedRootDAORequest
    success_url = reverse_lazy("web:crowd:profile-connected-users")
    template_name = "crowd/user/connected.html"
    template_name_suffix = "_form"

    def get_object(self) -> UserDTO:
        return self.request.user_dao.read_connected_user(self.kwargs["slug"])

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = {"user": self.get_object(), "object": self.get_object()}
        context.update(kwargs)
        return super().get_context_data(**context)

    def form_valid(self, form: ConnectedUserForm) -> HttpResponse:
        self.request.user_dao.update_connected_user(
            slug=self.kwargs["slug"], user_data=form.user_data
        )
        messages.success(self.request, _("Connected user updated successfully!"))
        return super().form_valid(form)

    def form_invalid(self, form: ConnectedUserForm) -> HttpResponse:
        messages.warning(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


class ProfileConnectedUserDeleteActionView(
    LoginRequiredMixin,
    SingleObjectTemplateResponseMixin,
    FormMixin,  # type: ignore [type-arg]
    ContextMixin,
    ProcessFormView,
):
    context_object_name = None
    form_class = forms.Form
    model = UserDTO
    pk_url_kwarg = "pk"
    query_pk_and_slug = False
    queryset = None
    request: AuthorizedRootDAORequest
    slug_field = "slug"
    slug_url_kwarg = "slug"
    success_url = reverse_lazy("web:crowd:profile-connected-users")
    template_name_suffix = "_confirm_delete"

    def get_object(self) -> UserDTO:
        return self.request.user_dao.read_connected_user(self.kwargs["slug"])

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = {"user": self.get_object()}
        context.update(kwargs)
        return super().get_context_data(**context)

    def form_valid(self, form: forms.Form) -> HttpResponseRedirect:  # noqa: ARG002
        success_url = self.get_success_url()
        self.request.user_dao.delete_connected_user(self.kwargs["slug"])
        messages.success(self.request, _("Connected user deleted successfully."))
        return HttpResponseRedirect(success_url)


class EventPageView(DetailView):  # type: ignore [type-arg]
    template_name = "chronology/event.html"
    model = Event
    context_object_name = "event"
    request: RootDAORequest

    def get_queryset(self) -> QuerySet[Event]:
        return (
            Event.objects.filter(sphere_id=self.request.root_dao.current_sphere.pk)
            .select_related("sphere")
            .prefetch_related(
                "spaces__agenda_items__session__tags__category",
                "spaces__agenda_items__session__session_participations__user",
                "spaces__agenda_items__session__proposal",
                "enrollment_configs",
                "filterable_tag_categories",
            )
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        # Get all sessions for this event that are published
        event_sessions = (
            Session.objects.filter(agenda_item__space__event=self.object)
            .select_related("proposal__host", "agenda_item__space", "sphere")
            .prefetch_related(
                "tags__category",
                "session_participations__user__manager",
                "session_participations__user__connected",
                "agenda_item__space__event__enrollment_configs",
            )
            .annotate(
                enrolled_count_cached=Count(
                    "session_participations",
                    filter=Q(
                        session_participations__status=SessionParticipationStatus.CONFIRMED
                    ),
                ),
                waiting_count_cached=Count(
                    "session_participations",
                    filter=Q(
                        session_participations__status=SessionParticipationStatus.WAITING
                    ),
                ),
            )
            .order_by("agenda_item__start_time")
        )

        hour_data = dict(self._get_hour_data(event_sessions))
        # Get session data objects that include enrollment status
        sessions_data = self._get_session_data(event_sessions)

        current_time = datetime.now(tz=UTC)
        ended_hour_data: dict[datetime, list[SessionData]] = defaultdict(list)
        current_hour_data: dict[datetime, list[SessionData]] = defaultdict(list)
        future_unavailable_hour_data: dict[datetime, list[SessionData]] = defaultdict(
            list
        )

        for session_data in sessions_data.values():
            session = session_data.session
            session_end_time = session.agenda_item.end_time
            session_start_time = session.agenda_item.start_time
            hour_key = session_start_time

            # Check if session has ended
            if session_end_time <= current_time:
                ended_hour_data[hour_key].append(session_data)
            elif (
                not session.is_enrollment_available
                and session_start_time > current_time
            ):
                future_unavailable_hour_data[hour_key].append(session_data)
            else:
                # Current sessions (available for enrollment or in progress)
                current_hour_data[hour_key].append(session_data)

        context.update(
            {
                "hour_data": hour_data,  # Keep original for backward compatibility
                "sessions": list(sessions_data.values()),
                "ended_hour_data": dict(ended_hour_data),
                "current_hour_data": dict(current_hour_data),
                "future_unavailable_hour_data": dict(future_unavailable_hour_data),
            }
        )

        # Add user enrollment config for authenticated users
        user_enrollment_config = None
        if self.request.user_dao and self.request.user_dao.user.email:
            user_enrollment_config = self.object.get_user_enrollment_config(
                self.request.user_dao.user.email
            )
        context["user_enrollment_config"] = user_enrollment_config

        # Check if any active enrollment config requires slots
        active_configs = self.object.get_active_enrollment_configs()
        requires_slots = any(
            config.restrict_to_configured_users for config in active_configs
        )
        context["enrollment_requires_slots"] = requires_slots

        # Handle anonymous mode
        # Clear anonymous session flags if user is authenticated
        if self.request.user_dao and self.request.session.get(
            "anonymous_enrollment_active"
        ):
            self.request.session.pop("anonymous_user_code", None)
            self.request.session.pop("anonymous_enrollment_active", None)
            self.request.session.pop("anonymous_event_id", None)
            self.request.session.pop("anonymous_site_id", None)
        elif (
            self.request.session.get("anonymous_enrollment_active")
            and not self.request.user_dao
        ):
            # Load anonymous user data if in anonymous mode - validate site
            anonymous_user_code = self.request.session.get("anonymous_user_code")
            current_site_id = self.request.root_dao.current_site.pk
            session_site_id = self.request.session.get("anonymous_site_id")
            if anonymous_user_code and session_site_id == current_site_id:
                anonymous_user_dao = self.request.root_dao.get_anonymous_user_dao()
                anonymous_user = None
                with suppress(NotFoundError):
                    anonymous_user = anonymous_user_dao.get_by_code(
                        code=anonymous_user_code
                    )

                if anonymous_user:
                    context["anonymous_code"] = anonymous_user.slug.removeprefix(
                        "code_"
                    )

                    # Get anonymous user's enrollments for this event
                    anonymous_enrollments = SessionParticipation.objects.filter(
                        user_id=anonymous_user.pk,
                        session__agenda_item__space__event=self.object,
                    ).select_related("session")

                    context["anonymous_user_enrollments"] = list(anonymous_enrollments)
                else:
                    # Clear anonymous session if site doesn't match
                    self.request.session.pop("anonymous_user_code", None)
                    self.request.session.pop("anonymous_enrollment_active", None)
                    self.request.session.pop("anonymous_event_id", None)
                    self.request.session.pop("anonymous_site_id", None)
            else:
                # Clear anonymous session if site doesn't match
                self.request.session.pop("anonymous_user_code", None)
                self.request.session.pop("anonymous_enrollment_active", None)
                self.request.session.pop("anonymous_event_id", None)
                self.request.session.pop("anonymous_site_id", None)

        # Add filterable tag categories for this event
        filterable_categories = self.object.filterable_tag_categories.all()
        context["filterable_tag_categories"] = list(filterable_categories)

        # Add proposals for superusers, sphere managers, and proposal authors
        if self.request.user_dao:
            # Check if user is a sphere manager for this event's sphere
            is_sphere_manager = self.object.sphere.managers.filter(
                id=self.request.user_dao.user.pk
            ).exists()

            if self.request.user_dao.user.is_superuser or is_sphere_manager:
                # Show all unaccepted proposals for superusers and sphere managers
                context["proposals"] = list(
                    Proposal.objects.filter(
                        category__event=self.object,
                        session__isnull=True,  # Only unaccepted proposals
                    )
                    .select_related("host", "category")
                    .prefetch_related("tags", "time_slots")
                    .order_by("-creation_time")
                )
            else:
                # Show only the user's own proposals
                context["proposals"] = list(
                    Proposal.objects.filter(
                        category__event=self.object,
                        session__isnull=True,  # Only unaccepted proposals
                        host_id=self.request.user_dao.user.pk,
                    )
                    .select_related("host", "category")
                    .prefetch_related("tags", "time_slots")
                    .order_by("-creation_time")
                )

        return context

    def _set_user_participations(
        self, sessions: dict[int, SessionData], event_sessions: QuerySet[Session]
    ) -> None:
        # Handle authenticated users
        if self.request.user_dao:
            # Get all connected users in a single query
            all_users = self.request.user_dao.users

            # Pre-fetch all participations for relevant users and sessions
            participations = SessionParticipation.objects.filter(
                session__in=event_sessions, user_id__in=[u.pk for u in all_users]
            ).select_related("user", "session")

            # Create lookup dictionaries for efficient access
            participation_by_user_session: dict[tuple[int, int], list[str]] = (
                defaultdict(list)
            )
            for p in participations:
                key = (p.user_id, p.session_id)
                participation_by_user_session[key].append(p.status)

            # Add user participation info for each session
            for user in all_users:
                for session in event_sessions:
                    statuses = set(
                        participation_by_user_session.get((user.pk, session.id), [])
                    )

                    sessions[session.id].has_any_enrollments |= bool(statuses)
                    sessions[session.id].user_enrolled |= (
                        SessionParticipationStatus.CONFIRMED in statuses
                    )
                    sessions[session.id].user_waiting |= (
                        SessionParticipationStatus.WAITING in statuses
                    )

        # Handle anonymous users
        elif self.request.session.get(
            "anonymous_enrollment_active"
        ) and self.request.session.get("anonymous_user_code"):
            # Validate anonymous user is for the current site
            current_site_id = self.request.root_dao.current_site.pk
            session_site_id = self.request.session.get("anonymous_site_id")
            try:
                anonymous_user_code = self.request.session["anonymous_user_code"]
            except (KeyError, ValueError):
                anonymous_user_code = None
            if session_site_id == current_site_id and anonymous_user_code is not None:
                anonymous_user_dao = self.request.root_dao.get_anonymous_user_dao()
                anonymous_user = None
                with suppress(NotFoundError):
                    anonymous_user = anonymous_user_dao.get_by_code(
                        code=anonymous_user_code
                    )

                if anonymous_user:
                    # Pre-fetch anonymous user participations for event sessions
                    anonymous_participations = SessionParticipation.objects.filter(
                        session__in=event_sessions, user_id=anonymous_user.pk
                    ).select_related("session")

                    # Create lookup dictionary for anonymous user
                    anonymous_participation_by_session: dict[int, list[str]] = (
                        defaultdict(list)
                    )
                    for p in anonymous_participations:
                        anonymous_participation_by_session[p.session_id].append(
                            p.status
                        )

                    # Add anonymous user participation info for each session
                    for session in event_sessions:
                        statuses = set(
                            anonymous_participation_by_session.get(session.id, [])
                        )

                        sessions[session.id].has_any_enrollments = bool(statuses)
                        sessions[session.id].user_enrolled = (
                            SessionParticipationStatus.CONFIRMED in statuses
                        )
                        sessions[session.id].user_waiting = (
                            SessionParticipationStatus.WAITING in statuses
                        )

    def _get_hour_data(
        self, event_sessions: QuerySet[Session]
    ) -> dict[datetime, list[SessionData]]:
        sessions_data = self._get_session_data(event_sessions)

        sessions_by_hour: dict[datetime, list[SessionData]] = defaultdict(list)
        for session in event_sessions:
            sessions_by_hour[session.agenda_item.start_time].append(
                sessions_data[session.id]
            )

        return sessions_by_hour

    def _get_session_data(
        self, event_sessions: QuerySet[Session]
    ) -> dict[int, SessionData]:
        sessions_data = {es.id: SessionData(session=es) for es in event_sessions}

        # Check if any active enrollment config has limit_to_end_time enabled
        active_configs = self.object.get_active_enrollment_configs()
        limit_configs = [c for c in active_configs if c.limit_to_end_time]
        current_time = datetime.now(tz=UTC)

        # Get the earliest end_time from configs with limit_to_end_time
        earliest_limit_end_time = None
        if limit_configs:
            earliest_limit_end_time = min(config.end_time for config in limit_configs)

        # Set filterable tags and display status for each session
        filterable_categories = set(self.object.filterable_tag_categories.all())
        for session_data in sessions_data.values():
            session_data.filterable_tags = [
                tag
                for tag in session_data.session.tags.all()
                if tag.category in filterable_categories
            ]

            session_start = session_data.session.agenda_item.start_time

            # Calculate if session is ongoing (has already started)
            session_data.is_ongoing = session_start <= current_time

            # Mark sessions as inactive for display based on limit_to_end_time rules
            if limit_configs and earliest_limit_end_time and session_data.is_ongoing:
                session_data.should_show_as_inactive = True

        # Set user participation data for authenticated users and anonymous users
        self._set_user_participations(sessions_data, event_sessions)

        return sessions_data


class EnrollmentChoice(StrEnum):
    CANCEL = auto()
    ENROLL = auto()
    WAITLIST = auto()
    BLOCK = auto()


@dataclass
class EnrollmentRequest:
    user: UserDTO
    choice: EnrollmentChoice
    name: str = _("yourself")


@dataclass
class Enrollments:
    cancelled_users: list[str]
    skipped_users: list[str]
    users_by_status: dict[SessionParticipationStatus, list[str]]

    def __init__(self) -> None:
        self.cancelled_users = []
        self.skipped_users = []
        self.users_by_status = defaultdict(list)
        super().__init__()


def _get_session_or_redirect(
    request: AuthorizedRootDAORequest, session_id: int
) -> Session:
    try:
        return Session.objects.get(
            sphere_id=request.root_dao.current_sphere.pk, id=session_id
        )
    except Session.DoesNotExist:
        raise RedirectError(
            reverse("web:index"), error=_("Session not found.")
        ) from None


_status_by_choice = {
    "enroll": SessionParticipationStatus.CONFIRMED,
    "waitlist": SessionParticipationStatus.WAITING,
}


class SessionEnrollPageView(LoginRequiredMixin, View):
    request: AuthorizedRootDAORequest

    def get(self, request: AuthorizedRootDAORequest, session_id: int) -> HttpResponse:
        session = _get_session_or_redirect(request, session_id)

        context = {
            "session": session,
            "event": session.agenda_item.space.event,
            "connected_users": self.request.user_dao.connected_users,
            "user_data": self._get_user_participation_data(session),
            "form": create_enrollment_form(
                session=session,
                users=self.request.user_dao.users,
                manager_email=self.request.user_dao.user.email,
            )(),
        }

        return TemplateResponse(request, "chronology/enroll_select.html", context)

    @staticmethod
    def _validate_request(session: Session) -> EnrollmentConfig:
        # Get the most liberal config for this session
        event = session.agenda_item.space.event
        if not (enrollment_config := event.get_most_liberal_config(session)):
            raise RedirectError(
                reverse(
                    "web:chronology:event",
                    kwargs={"slug": session.agenda_item.space.event.slug},
                ),
                error=_("No enrollment configuration is available for this session."),
            )

        # Note: UserDTO slot limits (max number of unique users that can be enrolled)
        # are handled in _process_enrollments(). Users can enroll in multiple sessions
        # without consuming additional slots. No need to block access here.

        return enrollment_config

    def _get_user_participation_data(
        self, session: Session
    ) -> list[SessionUserParticipationData]:
        user_data: list[SessionUserParticipationData] = []

        # Get all connected users with proper prefetching
        all_users = self.request.user_dao.users

        # Bulk fetch all participations for the event and users
        user_participations = SessionParticipation.objects.filter(
            user_id__in=[u.pk for u in all_users],
            session__agenda_item__space__event=session.agenda_item.space.event,
        ).select_related("session__agenda_item")

        # Group participations by user for efficient lookup
        participations_by_user: dict[int, list[SessionParticipation]] = defaultdict(
            list
        )
        for participation in user_participations:
            user_id = participation.user_id
            participations_by_user[user_id].append(participation)

        # Add enrollment status and time conflict info for each connected user
        for user in all_users:
            user_parts = participations_by_user.get(user.pk, [])

            data = SessionUserParticipationData(
                user=user,
                user_enrolled=any(
                    p.status == SessionParticipationStatus.CONFIRMED
                    and p.session == session
                    for p in user_parts
                ),
                user_waiting=any(
                    p.status == SessionParticipationStatus.WAITING
                    and p.session == session
                    for p in user_parts
                ),
                has_time_conflict=any(
                    session.agenda_item.overlaps_with(p.session.agenda_item)
                    for p in user_parts
                    if not (
                        p.session == session
                        and p.status == SessionParticipationStatus.CONFIRMED
                    )
                ),
            )
            user_data.append(data)

        return user_data

    def post(self, request: AuthorizedRootDAORequest, session_id: int) -> HttpResponse:
        session = _get_session_or_redirect(request, session_id)

        # Initialize form with POST data
        form_class = create_enrollment_form(
            session=session,
            users=self.request.user_dao.users,
            manager_email=self.request.user_dao.user.email,
        )
        form = form_class(data=request.POST)
        if not form.is_valid():
            # Add detailed form validation error messages without field name prefixes
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(self.request, str(error))

            # Check for specific enrollment restrictions and provide helpful messages
            enrollment_config = session.agenda_item.space.event.get_most_liberal_config(
                session
            )
            if enrollment_config and enrollment_config.restrict_to_configured_users:
                if not request.user_dao.user.email:
                    messages.error(
                        self.request,
                        _("Email address is required for enrollment in this session."),
                    )
                elif not session.agenda_item.space.event.get_user_enrollment_config(
                    request.user_dao.user.email
                ):
                    messages.error(
                        self.request,
                        _(
                            "Enrollment access permission is required for this "
                            "session. Please contact the organizers to obtain access."
                        ),
                    )
                else:
                    messages.warning(
                        self.request, _("Please review the enrollment options below.")
                    )
            else:
                messages.warning(
                    self.request, _("Please review the enrollment options below.")
                )

            # Re-render with form errors
            return TemplateResponse(
                request,
                "chronology/enroll_select.html",
                {
                    "session": session,
                    "event": session.agenda_item.space.event,
                    "connected_users": self.request.user_dao.connected_users,
                    "user_data": self._get_user_participation_data(session),
                    "form": form,
                },
            )

        # Only validate enrollment requirements when form is valid
        enrollment_config = self._validate_request(session)

        self._manage_enrollments(form, session, enrollment_config)

        return redirect(
            "web:chronology:event", slug=session.agenda_item.space.event.slug
        )

    def _get_enrollment_requests(self, form: forms.Form) -> list[EnrollmentRequest]:
        enrollment_requests = []
        for user in self.request.user_dao.users:
            # Skip inactive users
            if not user.is_active:
                continue
            user_field = f"user_{user.pk}"
            if form.cleaned_data.get(user_field):
                choice = form.cleaned_data[user_field]
                enrollment_requests.append(
                    EnrollmentRequest(
                        user=user, choice=EnrollmentChoice(choice), name=user.name
                    )
                )
        return enrollment_requests

    def _process_enrollments(
        self, enrollment_requests: list[EnrollmentRequest], session: Session
    ) -> Enrollments:
        enrollments = Enrollments()

        # Lock the session to prevent race conditions within the transaction
        session = Session.objects.select_for_update().get(id=session.id)
        participations = SessionParticipation.objects.filter(session=session).order_by(
            "creation_time"
        )

        for req in enrollment_requests:
            # Handle cancellation
            if req.choice == "cancel" and (
                existing_participation := next(
                    p for p in participations if p.user.id == req.user.pk
                )
            ):
                existing_participation.delete()
                enrollments.cancelled_users.append(req.name)

                # If this was a confirmed enrollment, promote from waiting list
                self._promote_from_waitlist(
                    existing_participation, participations, req, session, enrollments
                )
                continue

            self._check_and_create_enrollment(req, session, enrollments)
        return enrollments

    @staticmethod
    def _promote_from_waitlist(
        existing_participation: SessionParticipation,
        participations: QuerySet[SessionParticipation],
        req: EnrollmentRequest,
        session: Session,
        enrollments: Enrollments,
    ) -> None:
        if existing_participation.status == SessionParticipationStatus.CONFIRMED:
            for participation in participations:
                if (
                    participation.user.id != req.user.pk
                    and participation.status == SessionParticipationStatus.WAITING
                ) and not Session.objects.has_conflicts(
                    session, UserDTO.model_validate(participation.user)
                ):

                    can_be_promoted = True
                    if participation.user.email:
                        manager_user = participation.user
                        if participation.user.manager:
                            manager_user = participation.user.manager

                        user_config = (
                            session.agenda_item.space.event.get_user_enrollment_config(
                                manager_user.email
                            )
                        )
                        if user_config and not user_config.can_enroll_users(
                            [UserDTO.model_validate(participation.user)]
                        ):
                            can_be_promoted = False

                    if can_be_promoted:
                        participation.status = SessionParticipationStatus.CONFIRMED
                        participation.save()
                        enrollments.users_by_status[
                            SessionParticipationStatus.CONFIRMED
                        ].append(
                            f"{participation.user.get_full_name()} "
                            f"({_("promoted from waiting list")})"
                        )
                        break

    @staticmethod
    def _check_and_create_enrollment(
        req: EnrollmentRequest, session: Session, enrollments: Enrollments
    ) -> None:
        # Check if user is the session presenter
        if (
            Proposal.objects.filter(session=session).exists()
            and req.user.pk == session.proposal.host.id
        ):
            enrollments.skipped_users.append(f"{req.name} ({_('session host')!s})")
            return

        # Check for time conflicts for confirmed enrollment
        if req.choice == "enroll" and Session.objects.has_conflicts(session, req.user):
            enrollments.skipped_users.append(f"{req.name} ({_('time conflict')!s})")
            return

        # Use get_or_create to prevent duplicate enrollments in race conditions
        __, created = SessionParticipation.objects.get_or_create(
            session=session,
            user_id=req.user.pk,
            defaults={"status": _status_by_choice[req.choice]},
        )

        if created:
            enrollments.users_by_status[_status_by_choice[req.choice]].append(req.name)
        else:
            enrollments.skipped_users.append(f"{req.name} ({_('already enrolled')!s})")

    def _send_message(self, enrollments: Enrollments) -> None:
        for users, message in [
            (
                enrollments.users_by_status[SessionParticipationStatus.CONFIRMED],
                _("Enrolled: {}"),
            ),
            (
                enrollments.users_by_status[SessionParticipationStatus.WAITING],
                _("Added to waiting list: {}"),
            ),
            (enrollments.cancelled_users, _("Cancelled: {}")),
            (
                enrollments.skipped_users,
                _("Skipped (already enrolled or conflicts): {}"),
            ),
        ]:
            if users:
                messages.success(self.request, message.format(", ".join(users)))

    def _is_capacity_invalid(
        self,
        enrollment_requests: list[EnrollmentRequest],
        session: Session,
        enrollment_config: EnrollmentConfig,
    ) -> bool:
        confirmed_requests = [
            req for req in enrollment_requests if req.choice == "enroll"
        ]

        available_spots = enrollment_config.get_available_slots(session)

        if len(confirmed_requests) > available_spots:
            messages.error(
                self.request,
                str(
                    _(
                        "Not enough spots available. {} spots requested, {} available. "
                        "Please use waiting list for some users."
                    )
                ).format(len(confirmed_requests), available_spots),
            )
            return True

        return False

    def _manage_enrollments(
        self, form: forms.Form, session: Session, enrollment_config: EnrollmentConfig
    ) -> None:
        # Collect enrollment requests from form
        if enrollment_requests := self._get_enrollment_requests(form):
            # Validate capacity for confirmed enrollments (outside transaction)
            if self._is_capacity_invalid(
                enrollment_requests, session, enrollment_config
            ):
                raise RedirectError(
                    reverse(
                        "web:chronology:session-enrollment",
                        kwargs={"session_id": session.id},
                    )
                )

            # Use atomic transaction only for database operations
            with transaction.atomic():
                # Process enrollments and create success message
                enrollments = self._process_enrollments(enrollment_requests, session)

            # Send message outside transaction
            self._send_message(enrollments)
        else:
            raise RedirectError(
                reverse(
                    "web:chronology:session-enrollment",
                    kwargs={"session_id": session.id},
                ),
                warning=_("Please select at least one user to enroll."),
            )


class EventProposalPageView(LoginRequiredMixin, View):
    request: AuthorizedRootDAORequest

    def get(self, request: AuthorizedRootDAORequest, event_slug: str) -> HttpResponse:
        event = self._validate_event(event_slug)

        proposal_category = self._get_proposal_category(event)
        tag_categories = proposal_category.tag_categories.all()

        return TemplateResponse(
            request,
            "chronology/propose_session.html",
            {
                "event": event,
                "tag_categories": list(tag_categories),
                "confirmed_tags": {
                    str(category.id): (
                        category.tags.filter(confirmed=True).values("id", "name")
                    )
                    for category in tag_categories
                    if category.input_type == category.InputType.SELECT
                },
                "min_participants_limit": proposal_category.min_participants_limit,
                "max_participants_limit": proposal_category.max_participants_limit,
                "form": create_session_proposal_form(
                    proposal_category=ProposalCategoryDTO.model_validate(
                        proposal_category
                    ),
                    tag_categories=[
                        TagCategoryDTO.model_validate(tc)
                        for tc in proposal_category.tag_categories.all()
                    ],
                    tags={
                        tc.pk: [TagDTO.model_validate(t) for t in tc.tags.all()]
                        for tc in proposal_category.tag_categories.all()
                    },
                )(
                    initial={
                        "participants_limit": proposal_category.min_participants_limit
                    }
                ),
            },
        )

    def post(
        self, request: AuthorizedRootDAORequest, event_slug: str  # noqa: ARG002
    ) -> HttpResponse:
        event = self._validate_event(event_slug)
        proposal_category = self._get_proposal_category(event)

        return self._handle_form(proposal_category, event)

    def _handle_form(
        self, proposal_category: ProposalCategory, event: Event
    ) -> HttpResponse:
        # Initialize form with POST data
        form_class = create_session_proposal_form(
            proposal_category=ProposalCategoryDTO.model_validate(proposal_category),
            tag_categories=[
                TagCategoryDTO.model_validate(tc)
                for tc in proposal_category.tag_categories.all()
            ],
            tags={
                tc.pk: [TagDTO.model_validate(t) for t in tc.tags.all()]
                for tc in proposal_category.tag_categories.all()
            },
        )
        form = form_class(data=self.request.POST)

        if not form.is_valid():
            # Re-render with form errors
            tag_categories = proposal_category.tag_categories.all()

            return TemplateResponse(
                self.request,
                "chronology/propose_session.html",
                {
                    "event": event,
                    "tag_categories": list(tag_categories),
                    "confirmed_tags": {
                        str(category.id): list(
                            category.tags.filter(confirmed=True).values("id", "name")
                        )
                        for category in tag_categories
                        if category.input_type == category.InputType.SELECT
                    },
                    "min_participants_limit": proposal_category.min_participants_limit,
                    "max_participants_limit": proposal_category.max_participants_limit,
                    "form": form,
                },
            )

        # Create the proposal using form data
        proposal = Proposal.objects.create(
            category=proposal_category,
            host_id=self.request.user_dao.user.pk,
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            requirements=form.cleaned_data["requirements"],
            needs=form.cleaned_data["needs"],
            participants_limit=form.cleaned_data["participants_limit"],
            min_age=form.cleaned_data["min_age"],
        )

        for tag in self._get_tags(
            get_tag_data_from_form(form.cleaned_data), proposal_category
        ):
            proposal.tags.add(tag)

        messages.success(
            self.request,
            _("Session proposal '{}' submitted successfully!").format(
                form.cleaned_data["title"]
            ),
        )
        return redirect("web:chronology:event", slug=event.slug)

    @staticmethod
    def _get_tags(
        tag_data: dict[int, dict[str, list[str] | list[int]]],
        proposal_category: ProposalCategory,
    ) -> Generator[Tag]:
        for category_id, tags_info in tag_data.items():
            for tag_id in tags_info.get("selected_tags", []):
                with suppress(Tag.DoesNotExist), suppress(Tag.DoesNotExist):
                    tag = Tag.objects.get(id=tag_id)
                    yield tag

            for tag_name in tags_info.get("typed_tags", []):
                category = proposal_category.tag_categories.get(id=category_id)
                tag, _created = Tag.objects.get_or_create(
                    name=tag_name, category=category, defaults={"confirmed": False}
                )
                yield tag

    def _validate_event(self, event_slug: str) -> Event:
        try:
            event = Event.objects.get(
                sphere_id=self.request.root_dao.current_sphere.pk, slug=event_slug
            )
        except Event.DoesNotExist:
            raise RedirectError(
                reverse("web:index"), error=_("Event not found.")
            ) from None

        if not event.is_proposal_active:
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event_slug}),
                error=_("Proposal submission is not currently active for this event."),
            )

        return event

    @staticmethod
    def _get_proposal_category(event: Event) -> ProposalCategory:
        try:
            return ProposalCategory.objects.prefetch_related(
                "tag_categories__tags"
            ).get(event=event)
        except ProposalCategory.DoesNotExist:
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event.slug}),
                error=_(
                    "No proposal category configured for this event. "
                    "Please contact the organizers."
                ),
            ) from None


def _get_proposal(request: RootDAORequest, proposal_id: int) -> Proposal:
    try:
        proposal = Proposal.objects.get(
            category__event__sphere_id=request.root_dao.current_sphere.pk,
            id=proposal_id,
        )
    except Proposal.DoesNotExist:
        raise RedirectError(
            reverse("web:index"), error=_("Proposal not found.")
        ) from None

    # Check if proposal is already accepted
    if proposal.session:
        raise RedirectError(
            reverse(
                "web:chronology:event", kwargs={"slug": proposal.category.event.slug}
            ),
            warning=_("This proposal has already been accepted."),
        )

    return proposal


def _check_proposal_permission(user: UserDTO, proposal: Proposal) -> bool:
    if user.is_superuser or user.is_staff:
        return True

    # Check if user is a sphere manager for this event's sphere
    sphere = proposal.category.event.sphere
    return sphere.managers.filter(id=user.pk).exists()


class ProposalAcceptPageView(LoginRequiredMixin, View):
    def get(self, request: AuthorizedRootDAORequest, proposal_id: int) -> HttpResponse:
        proposal = _get_proposal(request, proposal_id)

        # Check permissions
        if not _check_proposal_permission(request.user_dao.user, proposal):
            raise RedirectError(
                reverse(
                    "web:chronology:event",
                    kwargs={"slug": proposal.category.event.slug},
                ),
                error=_(
                    "You don't have permission to accept proposals for this event."
                ),
            )

        event = proposal.category.event

        # Get available spaces and time slots for the event
        spaces = self._get_spaces(event)
        time_slots = self._get_time_slots(event)

        # Create the form
        form_class = create_proposal_acceptance_form(event)
        form = form_class()

        context = {
            "proposal": proposal,
            "event": event,
            "spaces": spaces,
            "time_slots": time_slots,
            "form": form,
        }

        return TemplateResponse(request, "chronology/accept_proposal.html", context)

    @staticmethod
    def _get_spaces(event: Event) -> list[Space]:
        spaces = Space.objects.filter(event=event)
        if not spaces.exists():
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event.slug}),
                error=_(
                    "No spaces configured for this event. Please create spaces first."
                ),
            )

        return list(spaces)

    @staticmethod
    def _get_time_slots(event: Event) -> list[TimeSlot]:
        time_slots = TimeSlot.objects.filter(event=event)

        if not time_slots.exists():
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event.slug}),
                error=_(
                    "No time slots configured for this event. "
                    "Please create time slots first."
                ),
            )

        return list(time_slots)


class ProposalAcceptConfirmAction(LoginRequiredMixin, View):
    def post(self, request: AuthorizedRootDAORequest, proposal_id: int) -> HttpResponse:
        proposal = _get_proposal(request, proposal_id)

        # Check permissions
        if not _check_proposal_permission(request.user_dao.user, proposal):
            raise RedirectError(
                reverse(
                    "web:chronology:event",
                    kwargs={"slug": proposal.category.event.slug},
                ),
                error=_(
                    "You don't have permission to accept proposals for this event."
                ),
            )

        event = proposal.category.event

        # Initialize form with POST data
        form_class = create_proposal_acceptance_form(event)
        form = form_class(data=request.POST)
        if not form.is_valid():
            # Re-render with form errors
            return TemplateResponse(
                request,
                "chronology/accept_proposal.html",
                {
                    "proposal": proposal,
                    "event": event,
                    "spaces": list(Space.objects.filter(event=event)),
                    "time_slots": list(TimeSlot.objects.filter(event=event)),
                    "form": form,
                },
            )

        self._create_session(form, proposal)

        messages.success(
            self.request,
            _("Proposal '{}' has been accepted and added to the agenda.").format(
                proposal.title
            ),
        )
        return redirect("web:chronology:event", slug=event.slug)

    @staticmethod
    def _create_session(form: forms.Form, proposal: Proposal) -> None:
        time_slot = form.cleaned_data["time_slot"]

        # Create a session from the proposal
        session = Session.objects.create(
            sphere=proposal.category.event.sphere,
            presenter_name=proposal.host.name,
            title=proposal.title,
            description=proposal.description,
            requirements=proposal.requirements,
            participants_limit=proposal.participants_limit,
            min_age=proposal.min_age,  # Copy minimum age requirement
            slug=slugify(proposal.title),
        )

        # Copy tags from proposal to session
        session.tags.set(proposal.tags.all())

        AgendaItem.objects.create(
            space=form.cleaned_data["space"],
            session=session,
            session_confirmed=True,
            start_time=time_slot.start_time,
            end_time=time_slot.end_time,
        )

        # Link proposal to session
        proposal.session = session
        proposal.save()


class ThemeSelectionActionView(View):
    @staticmethod
    def post(request: AuthorizedRootDAORequest) -> HttpResponse:
        form = ThemeSelectionForm(request.POST)
        if form.is_valid():
            theme = form.cleaned_data["theme"]
            request.session["theme"] = theme
            # Redirect back to the referring page
            return redirect(request.META.get("HTTP_REFERER", "/"))

        # If form is invalid, redirect back anyway
        return redirect(request.META.get("HTTP_REFERER", "/"))


class EventAnonymousActivateActionView(View):
    @staticmethod
    def get(request: RootDAORequest, event_slug: str) -> HttpResponse:
        # Redirect to event page if user is authenticated (not anonymous)
        if request.user_dao:
            return redirect("web:chronology:event", slug=event_slug)

        # Check if event exists and has anonymous enrollment enabled
        try:
            event = Event.objects.get(slug=event_slug)
        except Event.DoesNotExist:
            messages.error(request, _("Event not found."))
            return redirect("web:index")

        active_configs = event.get_active_enrollment_configs()

        if not any(
            config for config in active_configs if config.allow_anonymous_enrollment
        ):
            messages.error(
                request, _("Anonymous enrollment is not available for this event.")
            )
            return redirect("web:chronology:event", slug=event.slug)

        code = token_urlsafe(4).lower()
        # Create new anonymous UserDTO immediately
        anonymous_user_dao = request.root_dao.get_anonymous_user_dao()
        anonymous_user_dao.create_user(
            username=f"anon_{token_urlsafe(8).lower()}", slug=f"code_{code}"
        )

        # Set session flags - include site ID to prevent cross-site confusion
        request.session["anonymous_user_code"] = code
        request.session["anonymous_enrollment_active"] = True
        request.session["anonymous_event_id"] = event.id
        request.session["anonymous_site_id"] = request.root_dao.current_site.pk

        return redirect("web:chronology:event", slug=event.slug)


class SessionEnrollmentAnonymousPageView(View):
    @staticmethod
    def get(request: RootDAORequest, session_id: int) -> HttpResponse:
        # Redirect to regular enrollment if user is authenticated
        if request.user_dao:
            return redirect("web:chronology:session-enrollment", session_id=session_id)

        # Check if anonymous mode is active
        if not request.session.get("anonymous_enrollment_active"):
            messages.error(request, _("Anonymous enrollment is not active."))
            return redirect("web:index")

        # Check if anonymous user is for the current site
        current_site_id = request.root_dao.current_site.pk
        session_site_id = request.session.get("anonymous_site_id")
        if session_site_id != current_site_id:
            messages.error(
                request, _("Anonymous enrollment session is not valid for this site.")
            )
            return redirect("web:index")

        # Get session
        try:
            session = Session.objects.get(
                id=session_id, sphere__site_id=request.root_dao.current_site.pk
            )
        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")

        # Get anonymous user from session
        anonymous_user_code = request.session.get("anonymous_user_code")
        if not anonymous_user_code:
            messages.error(request, _("Anonymous session expired."))
            return redirect("web:index")

        anonymous_user_dao = request.root_dao.get_anonymous_user_dao()
        # Look up user by code
        try:
            anonymous_user = anonymous_user_dao.get_by_code(code=anonymous_user_code)
        except NotFoundError:
            messages.error(request, _("Anonymous user not found."))
            return redirect("web:index")

        # Check if user is already enrolled in THIS specific session
        existing_enrollment = SessionParticipation.objects.filter(
            session=session, user_id=anonymous_user.pk
        ).first()

        context = {
            "session": session,
            "event": session.agenda_item.space.event,
            "anonymous_user": anonymous_user,
            "anonymous_code": anonymous_user.slug.removeprefix("code_"),
            "needs_user_data": not anonymous_user.name,
            "existing_enrollment": existing_enrollment,
            "is_enrolled": existing_enrollment is not None,
        }

        return TemplateResponse(request, "chronology/anonymous_enroll.html", context)

    @staticmethod
    def post(request: RootDAORequest, session_id: int) -> HttpResponse:
        # Redirect to regular enrollment if user is authenticated
        if request.user_dao:
            return redirect("web:chronology:session-enrollment", session_id=session_id)

        # Check if anonymous mode is active
        if not request.session.get("anonymous_enrollment_active"):
            messages.error(request, _("Anonymous enrollment is not active."))
            return redirect("web:index")

        # Check if anonymous user is for the current site
        current_site_id = request.root_dao.current_site.pk
        session_site_id = request.session.get("anonymous_site_id")
        if session_site_id != current_site_id:
            messages.error(
                request, _("Anonymous enrollment session is not valid for this site.")
            )
            return redirect("web:index")

        # Get session
        try:
            session = Session.objects.get(
                id=session_id, sphere__site_id=request.root_dao.current_site.pk
            )
        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")

        # Get anonymous user
        anonymous_user_code = request.session.get("anonymous_user_code")
        if not anonymous_user_code:
            messages.error(request, _("Anonymous session expired."))
            return redirect("web:index")

        anonymous_user_dao = request.root_dao.get_anonymous_user_dao()
        # Look up user by code
        try:
            anonymous_user = anonymous_user_dao.get_by_code(code=anonymous_user_code)
        except NotFoundError:
            messages.error(request, _("Anonymous user not found."))
            return redirect("web:index")

        # Update user data if provided
        name = request.POST.get("name", "").strip()

        if name:
            anonymous_user.name = name

        # Validate required fields
        if not anonymous_user.name:
            messages.error(request, _("Name is required."))
            return redirect(
                "web:chronology:session-enrollment-anonymous", session_id=session_id
            )

        anonymous_user_dao.update_user_name(anonymous_user.slug, name)

        # Check for cancellation request
        action = request.POST.get("action", "enroll")

        if action == "cancel":
            # Cancel enrollment
            try:
                enrollment = SessionParticipation.objects.get(
                    session=session, user_id=anonymous_user.pk
                )
                enrollment.delete()
                messages.success(
                    request,
                    _("Successfully cancelled enrollment in session: %(title)s")
                    % {"title": session.title},
                )
            except SessionParticipation.DoesNotExist:
                messages.warning(request, _("No enrollment found to cancel."))
        else:
            # Check for time conflicts before enrolling
            if Session.objects.has_conflicts(session, anonymous_user):
                messages.error(
                    request,
                    _(
                        "Cannot enroll: You are already enrolled in another session "
                        "that conflicts with this time slot."
                    ),
                )
                return redirect(
                    "web:chronology:session-enrollment-anonymous", session_id=session_id
                )

            # Check if session is full and determine enrollment status
            if session.is_full:
                # Add to waitlist
                enrollment, created = SessionParticipation.objects.get_or_create(
                    session=session,
                    user_id=anonymous_user.pk,
                    defaults={"status": SessionParticipationStatus.WAITING.value},
                )

                messages.success(
                    request,
                    _(
                        "Session is full. You have been added to the waiting list "
                        "for: %(title)s"
                    )
                    % {"title": session.title},
                )
            else:
                # Enroll normally
                enrollment, created = SessionParticipation.objects.get_or_create(
                    session=session,
                    user_id=anonymous_user.pk,
                    defaults={"status": SessionParticipationStatus.CONFIRMED.value},
                )

                if (
                    not created
                    and enrollment.status != SessionParticipationStatus.CONFIRMED.value
                ):
                    enrollment.status = SessionParticipationStatus.CONFIRMED.value
                    enrollment.save()

                messages.success(
                    request,
                    _("Successfully enrolled in session: %(title)s")
                    % {"title": session.title},
                )

        return redirect(
            "web:chronology:event", slug=session.agenda_item.space.event.slug
        )


class AnonymousLoadActionView(View):
    """Handle entering an anonymous code to load a previous session"""

    @staticmethod
    def post(request: RootDAORequest) -> HttpResponse:
        # Only accessible to non-authenticated users
        if request.user_dao:
            return redirect("web:index")

        code = request.POST.get("code", "").strip()

        if not code:
            messages.error(request, _("Please enter a code."))
            # Try to redirect back to the referring event
            referer = request.META.get("HTTP_REFERER", "")
            if "event" in referer:
                return redirect(referer)
            return redirect("web:index")

        anonymous_user_dao = request.root_dao.get_anonymous_user_dao()
        # Look up user by code
        try:
            anonymous_user = anonymous_user_dao.get_by_code(code=code)
        except NotFoundError:
            messages.error(request, _("Invalid code. Please check and try again."))
            # Try to redirect back to the referring event
            referer = request.META.get("HTTP_REFERER", "")
            if "event" in referer:
                return redirect(referer)
            return redirect("web:index")

        # Get user's enrollments to find the event and site
        enrollments = SessionParticipation.objects.filter(
            user_id=anonymous_user.pk
        ).select_related("session__agenda_item__space__event", "session__sphere")

        if not (first_enrollment := enrollments.first()):
            messages.warning(request, _("No enrollments found for this code."))
            return redirect("web:index")

        # Get the first enrollment to determine the event and site
        event = first_enrollment.session.agenda_item.space.event
        site_id = first_enrollment.session.sphere.site_id

        # Load user into session with proper site association
        request.session["anonymous_user_code"] = code
        request.session["anonymous_enrollment_active"] = True
        request.session["anonymous_event_id"] = event.id
        request.session["anonymous_site_id"] = site_id

        messages.success(
            request, _("Code loaded successfully. You can now manage your enrollments.")
        )
        return redirect("web:chronology:event", slug=event.slug)


class AnonymousResetActionView(View):
    @staticmethod
    def get(request: HttpRequest) -> HttpResponse:
        event_id = request.session.get("anonymous_event_id")

        event = None
        if event_id:
            event = Event.objects.filter(id=event_id).first()

        # Clear current anonymous session data
        request.session.pop("anonymous_user_code", None)
        request.session.pop("anonymous_enrollment_active", None)
        request.session.pop("anonymous_event_id", None)
        request.session.pop("anonymous_site_id", None)

        if event:
            # Create new anonymous session (which generates new code)
            return redirect(
                "web:chronology:event-anonymous-activate", event_slug=event.slug
            )
        return redirect("web:index")


def get_discord_username(request: RootDAORequest, user_slug: str) -> HttpResponse:
    """Return Discord username HTML fragment via htmx.

    Args:
        request: HTTP request
        user_slug: Slug of user whose Discord username to fetch

    Returns:
        TemplateResponse with Discord username fragment
    """
    other_user_dao = request.root_dao.get_other_user_dao()
    user = other_user_dao.get_user_by_slug(user_slug)
    if user.discord_username:
        return TemplateResponse(
            request,
            "chronology/_discord_username.html",
            {"discord_username": user.discord_username},
        )
    return HttpResponse("")  # Return empty if no discord username
