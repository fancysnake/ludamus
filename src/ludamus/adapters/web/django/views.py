import json
import logging
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from secrets import token_urlsafe
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import quote_plus, urlencode, urlparse

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout as django_logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.generic.base import ContextMixin, RedirectView, TemplateView, View
from django.views.generic.detail import DetailView, SingleObjectTemplateResponseMixin
from django.views.generic.edit import FormMixin, ProcessFormView

from ludamus.adapters.db.django.models import (
    MAX_CONNECTED_USERS,
    EnrollmentConfig,
    Event,
    Proposal,
    ProposalCategory,
    Session,
    SessionParticipation,
    SessionParticipationStatus,
    Tag,
    can_enroll_users,
)
from ludamus.adapters.oauth import oauth
from ludamus.adapters.web.django.entities import (
    SessionData,
    SessionUserParticipationData,
    TagCategoryData,
    TagWithCategory,
)
from ludamus.mills import (
    AcceptProposalService,
    AnonymousEnrollmentService,
    get_user_enrollment_config,
)
from ludamus.pacts import (
    AgendaItemDTO,
    AreaDTO,
    AuthenticatedRequestContext,
    DependencyInjectorProtocol,
    EventDTO,
    LocationData,
    NotFoundError,
    ProposalCategoryDTO,
    ProposalDTO,
    ProposalRepositoryProtocol,
    RequestContext,
    SessionDTO,
    SpaceDTO,
    TagCategoryDTO,
    TagDTO,
    UserData,
    UserDTO,
    UserParticipation,
    VenueDTO,
)

from .exceptions import RedirectError
from .forms import (
    ConnectedUserForm,
    UserForm,
    create_enrollment_form,
    create_proposal_acceptance_form,
    create_session_proposal_form,
    get_tag_data_from_form,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Generator

    from django.db.models.query import QuerySet

MINIMUM_ALLOWED_USER_AGE = 16
CACHE_TIMEOUT = 600  # 10 minutes


class AuthenticatedRootRequest(HttpRequest):
    context: AuthenticatedRequestContext
    di: DependencyInjectorProtocol


class RootRequest(HttpRequest):
    context: RequestContext
    di: DependencyInjectorProtocol


class LoginRequiredPageView(TemplateView):
    template_name = "crowd/login_required.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        # Variables for login_button.html component
        context["show_icon"] = True
        context["text"] = ""
        context["extra_class"] = ""
        return context


class Auth0LoginActionView(View):
    @staticmethod
    def get(request: RootRequest) -> HttpResponse:
        """Redirect to Auth0 for authentication.

        Returns:
            HttpResponse: Redirect to Auth0 authorization endpoint.

        Raises:
            RedirectError: If the request is not from the root domain.
        """
        root_domain = request.di.uow.spheres.read_site(
            request.context.root_sphere_id
        ).domain
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
    request: RootRequest

    def get_redirect_url(self, *args: Any, **kwargs: Any) -> str | None:
        redirect_to = super().get_redirect_url(*args, **kwargs)

        # Validate state parameter
        if not (state_token := self.request.GET.get("state")):
            messages.error(
                self.request,
                _("Invalid authentication request: missing state parameter"),
            )
            return self.request.build_absolute_uri(reverse("web:index"))

        # Retrieve and validate state data
        cache_key = f"oauth_state:{state_token}"

        if not (state_data_json := cache.get(cache_key)):
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

        except KeyError, ValueError:
            messages.error(self.request, _("Invalid authentication state"))
            return self.request.build_absolute_uri(reverse("web:index"))

        if self.request.context.current_user_slug:
            return redirect_to or self.request.build_absolute_uri(reverse("web:index"))

        userinfo = self._get_userinfo()
        username = self._get_username(userinfo)
        email = userinfo.get("email") if isinstance(userinfo, dict) else None
        avatar_url = userinfo.get("picture") if isinstance(userinfo, dict) else None
        display_name = self._get_display_name(userinfo)

        # Handle login/signup
        if not self.request.context.current_user_slug:
            try:
                user = self.request.di.uow.active_users.read_by_username(username)
            except NotFoundError:
                slug = slugify(username)
                self.request.di.uow.active_users.create(
                    UserData(
                        slug=slug,
                        username=username,
                        password=make_password(None),
                        email=email or "",
                        avatar_url=avatar_url or "",
                        name=display_name or "",
                    )
                )
                user = self.request.di.uow.active_users.read_by_username(username)

            # Log the user in
            self.request.di.uow.login_user(self.request, user.slug)
            if self.request.session.get("anonymous_enrollment_active"):
                self.request.session.pop("anonymous_user_code", None)
                self.request.session.pop("anonymous_enrollment_active", None)
                self.request.session.pop("anonymous_event_id", None)
            messages.success(self.request, _("Welcome!"))

        update_data: UserData = {}
        if email and user.email != email:
            update_data["email"] = email
        if avatar_url and user.avatar_url != avatar_url:
            update_data["avatar_url"] = avatar_url
        if display_name and not (user.name or "").strip():
            update_data["name"] = display_name
        if update_data:
            self.request.di.uow.active_users.update(user.slug, update_data)

            if "name" in update_data:
                user = self.request.di.uow.active_users.read(user.slug)

        if not self.request.context.current_user_slug and not (user.name or "").strip():
            messages.success(self.request, _("Please complete your profile."))
            if redirect_to:
                parsed = urlparse(redirect_to)
                return (
                    f'{parsed.scheme}://{parsed.netloc}{reverse("web:crowd:profile")}'
                )
            return self.request.build_absolute_uri(reverse("web:crowd:profile"))

        return redirect_to or self.request.build_absolute_uri(reverse("web:index"))

    def _get_userinfo(self) -> dict[str, Any]:
        token = oauth.auth0.authorize_access_token(self.request)
        if isinstance(token, dict):
            userinfo = token.get("userinfo")
            if isinstance(userinfo, dict) and userinfo:
                logger.info(
                    "Auth0 userinfo from token: sub=%s provider=%s has_name=%s ts=%s",
                    userinfo.get("sub"),
                    userinfo.get("identities", [{}])[0].get("provider"),
                    bool(userinfo.get("name")),
                    timezone.now().isoformat(),
                )
                return userinfo
        try:
            userinfo = oauth.auth0.userinfo(token=token)
        except Exception as exc:
            raise RedirectError(
                reverse("web:index"), error=_("Authentication failed")
            ) from exc
        if isinstance(userinfo, dict) and userinfo:
            logger.info(
                "Auth0 userinfo via /userinfo: sub=%s provider=%s has_name=%s ts=%s",
                userinfo.get("sub"),
                userinfo.get("identities", [{}])[0].get("provider"),
                bool(userinfo.get("name")),
                timezone.now().isoformat(),
            )
        return userinfo if isinstance(userinfo, dict) else {}

    @staticmethod
    def _get_display_name(userinfo: dict[str, Any]) -> str | None:
        name = userinfo.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()

        given = userinfo.get("given_name")
        family = userinfo.get("family_name")
        parts = [
            part.strip()
            for part in (given, family)
            if isinstance(part, str) and part.strip()
        ]
        if parts:
            return " ".join(parts)

        nickname = userinfo.get("nickname")
        if isinstance(nickname, str) and nickname.strip():
            return nickname.strip()

        preferred = userinfo.get("preferred_username")
        if isinstance(preferred, str) and preferred.strip():
            return preferred.strip()

        return None

    @staticmethod
    def _get_username(userinfo: dict[str, Any]) -> str:
        try:
            return f'auth0|{userinfo["sub"]}'
        except KeyError as exc:
            raise RedirectError(
                reverse("web:index"), error=_("Authentication failed")
            ) from exc


class Auth0LogoutActionView(RedirectView):
    request: RootRequest

    def get_redirect_url(self, *args: Any, **kwargs: Any) -> str | None:
        redirect_to = super().get_redirect_url(*args, **kwargs)

        django_logout(self.request)

        last_domain = self.request.di.uow.spheres.read_site(
            self.request.context.current_sphere_id
        ).domain
        messages.success(self.request, _("You have been successfully logged out."))

        return _auth0_logout_url(
            self.request, last_domain=last_domain, redirect_to=redirect_to
        )


def _auth0_logout_url(
    request: RootRequest,
    *,
    last_domain: str | None = None,
    redirect_to: str | None = None,
) -> str:
    root_domain = request.di.uow.spheres.read_site(
        request.context.root_sphere_id
    ).domain
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
    request: RootRequest
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
            # Also allow subdomains of ROOT_DOMAIN if configured
            if (
                last_domain.endswith(f".{settings.ROOT_DOMAIN}")
                or last_domain == settings.ROOT_DOMAIN
            ):
                return f"{self.request.scheme}://{last_domain}{redirect_url}"

            # Check against explicitly allowed domains
            try:
                last_sphere = self.request.di.uow.spheres.read_by_domain(last_domain)
            except NotFoundError:
                last_sphere = None

            if last_sphere:
                return f"{self.request.scheme}://{last_domain}{redirect_url}"

            messages.warning(self.request, _("Invalid domain for redirect."))

        return redirect_url


EVENT_PLACEHOLDER_IMAGES = [
    "placeholder-images/01.jpg",  # meeples
    "placeholder-images/02.jpg",  # chess
    "placeholder-images/03.jpg",  # cards
    "placeholder-images/04.jpg",  # dice
    "placeholder-images/05.jpg",  # tabletop
    "placeholder-images/06.jpg",  # chess pieces
    "placeholder-images/07.jpg",  # board game
    "placeholder-images/08.jpg",  # retro arcade
    "placeholder-images/09.jpg",  # controller
    "placeholder-images/10.png",  # arcade
]


@dataclass
class EventData:  # pylint: disable=too-many-instance-attributes
    cover_image_url: str
    description: str
    end_time: datetime
    is_ended: bool
    is_live: bool
    is_proposal_active: bool
    name: str
    session_count: int
    start_time: datetime
    slug: str

    @classmethod
    def from_event(
        cls, *, event: Event, session_count: int, cover_image_url: str
    ) -> Self:
        return cls(
            cover_image_url=cover_image_url,
            description=event.description,
            end_time=event.end_time,
            is_ended=event.is_ended,
            is_live=event.is_live,
            is_proposal_active=event.is_proposal_active,
            name=event.name,
            session_count=session_count,
            slug=event.slug,
            start_time=event.start_time,
        )


class IndexPageView(TemplateView):
    request: RootRequest
    template_name = "index.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        all_events = list(
            Event.objects.filter(sphere_id=self.request.context.current_sphere_id)
            .annotate(session_count=Count("venues__areas__spaces__agenda_items"))
            .order_by("start_time")
            .all()
        )
        event_datas: list[EventData] = []
        # Assign placeholder images based on index
        for i, event in enumerate(all_events):
            img = EVENT_PLACEHOLDER_IMAGES[i % len(EVENT_PLACEHOLDER_IMAGES)]
            event_datas.append(
                EventData.from_event(
                    event=event,
                    session_count=event.session_count,
                    cover_image_url=staticfiles_storage.url(img),
                )
            )
        context["upcoming_events"] = [e for e in event_datas if not e.is_ended]
        context["past_events"] = [e for e in event_datas if e.is_ended]
        return context


class ProfilePageView(
    LoginRequiredMixin,
    SingleObjectTemplateResponseMixin,
    FormMixin,  # type: ignore [type-arg]
    ContextMixin,
    ProcessFormView,
):
    form_class = UserForm
    request: AuthenticatedRootRequest
    success_url = reverse_lazy("web:index")
    template_name = "crowd/user/edit.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        kwargs["user"] = self.request.di.uow.active_users.read(
            self.request.context.current_user_slug
        )
        kwargs["object"] = self.request.di.uow.active_users.read(
            self.request.context.current_user_slug
        )
        kwargs["confirmed_participations_count"] = SessionParticipation.objects.filter(
            user_id=self.request.context.current_user_id,
            status=SessionParticipationStatus.CONFIRMED,
        ).count()
        return super().get_context_data(**kwargs)

    def form_valid(self, form: UserForm) -> HttpResponse:
        # Check if email is being changed and if it already exists
        email = form.user_data.get("email", "").strip()
        if email and self.request.di.uow.active_users.email_exists(
            email, exclude_slug=self.request.context.current_user_slug
        ):
            form.add_error(
                "email",
                _(
                    "This email address is already in use. "
                    "Please use a different email address."
                ),
            )
            return self.form_invalid(form)

        self.request.di.uow.active_users.update(
            self.request.context.current_user_slug, form.user_data
        )
        messages.success(self.request, _("Profile updated successfully!"))
        return super().form_valid(form)

    def form_invalid(self, form: forms.Form) -> HttpResponse:
        messages.warning(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)

    def get_initial(self) -> dict[str, Any]:
        return self.request.di.uow.active_users.read(
            self.request.context.current_user_slug
        ).model_dump()


class ProfileConnectedUsersPageView(
    LoginRequiredMixin,
    SingleObjectTemplateResponseMixin,
    FormMixin,  # type: ignore [type-arg]
    ContextMixin,
    ProcessFormView,
):
    form_class = ConnectedUserForm
    object: UserDTO
    request: AuthenticatedRootRequest
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
            for connected in self.request.di.uow.connected_users.read_all(
                self.request.context.current_user_slug
            )
        ]
        context["connected_users"] = connected_users
        context["max_connected_users"] = MAX_CONNECTED_USERS
        return context

    def form_valid(self, form: ConnectedUserForm) -> HttpResponse:
        # Check if user has reached the maximum number of connected users

        connected_count = len(
            self.request.di.uow.connected_users.read_all(
                self.request.context.current_user_slug
            )
        )
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
        self.request.di.uow.connected_users.create(
            self.request.context.current_user_slug, user_data=user_data
        )
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
    request: AuthenticatedRootRequest
    success_url = reverse_lazy("web:crowd:profile-connected-users")
    template_name = "crowd/user/connected.html"
    template_name_suffix = "_form"

    def get_object(self) -> UserDTO:
        return self.request.di.uow.connected_users.read(
            self.request.context.current_user_slug, self.kwargs["slug"]
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = {
            "user": self.get_object(),
            "object": self.get_object(),
            "max_connected_users": MAX_CONNECTED_USERS,
            "connected_users": [
                {
                    "user": connected,
                    "form": ConnectedUserForm(initial=connected.model_dump()),
                }
                for connected in self.request.di.uow.connected_users.read_all(
                    self.request.context.current_user_slug
                )
            ],
        }
        context.update(kwargs)
        return super().get_context_data(**context)

    def form_valid(self, form: ConnectedUserForm) -> HttpResponse:
        self.request.di.uow.connected_users.update(
            manager_slug=self.request.context.current_user_slug,
            user_slug=self.kwargs["slug"],
            user_data=form.user_data,
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
    request: AuthenticatedRootRequest
    slug_field = "slug"
    slug_url_kwarg = "slug"
    success_url = reverse_lazy("web:crowd:profile-connected-users")
    template_name_suffix = "_confirm_delete"

    def form_valid(self, form: forms.Form) -> HttpResponseRedirect:  # noqa: ARG002
        success_url = self.get_success_url()
        self.request.di.uow.connected_users.delete(
            self.request.context.current_user_slug, self.kwargs["slug"]
        )
        messages.success(self.request, _("Connected user deleted successfully."))
        return HttpResponseRedirect(success_url)


class UserDiscordUsernameComponentView(View):
    """Return Discord username HTML fragment via htmx."""

    request: RootRequest

    @staticmethod
    def get(request: RootRequest, user_slug: str) -> HttpResponse:
        try:
            user = request.di.uow.active_users.read(user_slug)
        except NotFoundError:
            return HttpResponse(status=404)
        if user.discord_username:
            return TemplateResponse(
                request,
                "crowd/user/parts/discord_username.html",
                {"discord_username": user.discord_username},
            )
        return HttpResponse("")


class EventPageView(DetailView):  # type: ignore [type-arg]
    template_name = "chronology/event.html"
    model = Event
    context_object_name = "event"
    request: RootRequest

    def get_queryset(self) -> QuerySet[Event]:
        return (
            Event.objects.filter(sphere_id=self.request.context.current_sphere_id)
            .select_related("sphere")
            .prefetch_related(
                "venues__areas__spaces__agenda_items__session__tags__category",
                "venues__areas__spaces__agenda_items__session__session_participations__user",
                "venues__areas__spaces__agenda_items__session__proposal",
                "enrollment_configs",
                "filterable_tag_categories",
            )
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        # Get all sessions for this event that are published
        event_sessions = (
            Session.objects.filter(agenda_item__space__area__venue__event=self.object)
            .select_related("proposal__host", "agenda_item__space", "sphere")
            .prefetch_related(
                "tags__category",
                "session_participations__user__manager",
                "session_participations__user__connected",
                "agenda_item__space__area__venue__event__enrollment_configs",
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
            session_end_time = session_data.agenda_item.end_time
            session_start_time = session_data.agenda_item.start_time
            hour_key = session_start_time
            # Check if session has ended
            if session_end_time <= current_time:
                ended_hour_data[hour_key].append(session_data)
            elif (
                not session_data.is_enrollment_available
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
                "total_enrolled": sum(s.enrolled_count for s in sessions_data.values()),
                "user_enrolled_sessions": [
                    s for s in sessions_data.values() if s.user_enrolled
                ],
            }
        )

        # Add user enrollment config for authenticated users
        user_enrollment_config = None
        if (
            self.request.context.current_user_slug
            and self.request.di.uow.active_users.read(
                self.request.context.current_user_slug
            ).email
        ):
            user_enrollment_config = get_user_enrollment_config(
                event=EventDTO.model_validate(self.object),
                user_email=self.request.di.uow.active_users.read(
                    self.request.context.current_user_slug
                ).email,
                enrollment_config_repo=self.request.di.uow.enrollment_configs,
                ticket_api=self.request.di.ticket_api,
                check_interval_minutes=settings.MEMBERSHIP_API_CHECK_INTERVAL,
            )
        context["user_enrollment_config"] = user_enrollment_config

        # Check if any active enrollment config requires slots
        active_configs = self.object.get_active_enrollment_configs()
        requires_slots = any(
            config.restrict_to_configured_users for config in active_configs
        )
        context["enrollment_requires_slots"] = requires_slots
        anonymous_service = AnonymousEnrollmentService(
            self.request.di.uow.anonymous_users
        )

        # Handle anonymous mode
        # Clear anonymous session flags if user is authenticated
        if self.request.context.current_user_id and self.request.session.get(
            "anonymous_enrollment_active"
        ):
            self.request.session.pop("anonymous_user_code", None)
            self.request.session.pop("anonymous_enrollment_active", None)
            self.request.session.pop("anonymous_event_id", None)
            self.request.session.pop("anonymous_site_id", None)
        elif (
            self.request.session.get("anonymous_enrollment_active")
            and not self.request.context.current_user_id
        ):
            # Load anonymous user data if in anonymous mode - validate site
            anonymous_user_code = self.request.session.get("anonymous_user_code")
            current_site_id = self.request.context.current_site_id
            session_site_id = self.request.session.get("anonymous_site_id")
            if anonymous_user_code and session_site_id == current_site_id:
                anonymous_user = None
                with suppress(NotFoundError):
                    anonymous_user = anonymous_service.get_user_by_code(
                        code=anonymous_user_code
                    )

                if anonymous_user:
                    context["anonymous_code"] = anonymous_user.slug.removeprefix(
                        "code_"
                    )

                    # Get anonymous user's enrollments for this event
                    anonymous_enrollments = SessionParticipation.objects.filter(
                        user_id=anonymous_user.pk,
                        session__agenda_item__space__area__venue__event=self.object,
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
        if self.request.context.current_user_slug:
            # Check if user is a sphere manager for this event's sphere
            is_sphere_manager = self.object.sphere.managers.filter(
                id=self.request.context.current_user_id
            ).exists()

            if (
                self.request.di.uow.active_users.read(
                    self.request.context.current_user_slug
                ).is_superuser
                or is_sphere_manager
            ):
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
                        host_id=self.request.context.current_user_id,
                    )
                    .select_related("host", "category")
                    .prefetch_related("tags", "time_slots")
                    .order_by("-creation_time")
                )

        return context

    def _set_user_participations(
        self, sessions: dict[int, SessionData], event_sessions: QuerySet[Session]
    ) -> None:
        anonymous_service = AnonymousEnrollmentService(
            self.request.di.uow.anonymous_users
        )
        # Handle authenticated users
        if self.request.context.current_user_slug:
            # Get all connected users in a single query
            all_users = [
                self.request.di.uow.active_users.read(
                    self.request.context.current_user_slug
                ),
                *self.request.di.uow.connected_users.read_all(
                    self.request.context.current_user_slug
                ),
            ]

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
            current_site_id = self.request.context.current_site_id
            session_site_id = self.request.session.get("anonymous_site_id")
            anonymous_user_code = self.request.session.get("anonymous_user_code")
            if session_site_id == current_site_id and anonymous_user_code is not None:
                anonymous_user = None
                with suppress(NotFoundError):
                    anonymous_user = anonymous_service.get_user_by_code(
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
        sessions_data = {}
        for session in event_sessions:
            area = getattr(
                session.agenda_item.space, "area", None
            )  # TODO(fancysnake): Fix after merging venues
            presenter_name = session.presenter_name or ""
            presenter = SimpleNamespace(
                full_name=presenter_name,
                name=presenter_name,
                username=presenter_name,
                avatar_url=None,
                gravatar_url=None,
            )
            sessions_data[session.id] = SessionData(
                effective_participants_limit=session.effective_participants_limit,
                full_participant_info=session.full_participant_info,
                agenda_item=AgendaItemDTO.model_validate(session.agenda_item),
                session=SessionDTO.model_validate(session),
                presenter=presenter,
                tags=[
                    TagWithCategory(
                        category=TagCategoryData(
                            icon=t.category.icon, name=t.category.name, pk=t.category.pk
                        ),
                        category_id=t.category_id,
                        confirmed=t.confirmed,
                        name=t.name,
                        pk=t.pk,
                    )
                    for t in session.tags.select_related("category").all()
                ],
                proposal=(
                    ProposalDTO.model_validate(session.proposal)
                    if Proposal.objects.filter(session=session).exists()
                    else None
                ),
                is_enrollment_available=session.is_enrollment_available,
                is_full=session.is_full,
                loc=LocationData(
                    space=SpaceDTO.model_validate(session.agenda_item.space),
                    area=(  # TODO(fancysnake): Fix after merging venues
                        AreaDTO.model_validate(area) if area else None
                    ),
                    venue=(  # TODO(fancysnake): Fix after merging venues
                        VenueDTO.model_validate(area.venue) if area else None
                    ),
                ),
                enrolled_count=session.enrolled_count,
                session_participations=[
                    UserParticipation.model_validate(sp)
                    for sp in session.session_participations.all()
                ],
            )

        # Check if any active enrollment config has limit_to_end_time enabled
        active_configs = self.object.get_active_enrollment_configs()
        limit_configs = [c for c in active_configs if c.limit_to_end_time]
        current_time = datetime.now(tz=UTC)

        # Get the earliest end_time from configs with limit_to_end_time
        earliest_limit_end_time = None
        if limit_configs:
            earliest_limit_end_time = min(config.end_time for config in limit_configs)

        # Set filterable tags and display status for each session
        filterable_categories = set(
            self.object.filterable_tag_categories.all().values_list("id", flat=True)
        )
        for session_data in sessions_data.values():
            session_data.filterable_tags = [
                tag
                for tag in session_data.tags
                if tag.category_id in filterable_categories
            ]

            session_start = session_data.agenda_item.start_time

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
    request: AuthenticatedRootRequest, session_id: int
) -> Session:
    try:
        return Session.objects.get(
            sphere_id=request.context.current_sphere_id, id=session_id
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
    request: AuthenticatedRootRequest

    def get(self, request: AuthenticatedRootRequest, session_id: int) -> HttpResponse:
        session = _get_session_or_redirect(request, session_id)

        context = {
            "session": session,
            "event": session.agenda_item.space.area.venue.event,
            "connected_users": self.request.di.uow.connected_users.read_all(
                self.request.context.current_user_slug
            ),
            "user_data": self._get_user_participation_data(session),
            "form": create_enrollment_form(
                session=session,
                current_user=self.request.di.uow.active_users.read(
                    self.request.context.current_user_slug
                ),
                connected_users=self.request.di.uow.connected_users.read_all(
                    self.request.context.current_user_slug
                ),
                enrollment_config_repo=request.di.uow.enrollment_configs,
                ticket_api=request.di.ticket_api,
            )(),
        }

        return TemplateResponse(request, "chronology/enroll_select.html", context)

    @staticmethod
    def _validate_request(session: Session) -> EnrollmentConfig:
        # Get the most liberal config for this session
        event = session.agenda_item.space.area.venue.event
        if not (enrollment_config := event.get_most_liberal_config(session)):
            raise RedirectError(
                reverse(
                    "web:chronology:event",
                    kwargs={"slug": session.agenda_item.space.area.venue.event.slug},
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
        all_users = [
            self.request.di.uow.active_users.read(
                self.request.context.current_user_slug
            ),
            *self.request.di.uow.connected_users.read_all(
                self.request.context.current_user_slug
            ),
        ]

        # Bulk fetch all participations for the event and users
        user_participations = SessionParticipation.objects.filter(
            user_id__in=[u.pk for u in all_users],
            session__agenda_item__space__area__venue__event=session.agenda_item.space.area.venue.event,
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
                    if p.session != session
                ),
            )
            user_data.append(data)

        return user_data

    def post(self, request: AuthenticatedRootRequest, session_id: int) -> HttpResponse:
        session = _get_session_or_redirect(request, session_id)

        # Initialize form with POST data
        form_class = create_enrollment_form(
            session=session,
            current_user=self.request.di.uow.active_users.read(
                self.request.context.current_user_slug
            ),
            connected_users=self.request.di.uow.connected_users.read_all(
                self.request.context.current_user_slug
            ),
            enrollment_config_repo=request.di.uow.enrollment_configs,
            ticket_api=request.di.ticket_api,
        )
        form = form_class(data=request.POST)
        if not form.is_valid():
            # Add detailed form validation error messages without field name prefixes
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(self.request, str(error))

            # Check for specific enrollment restrictions and provide helpful messages
            enrollment_config = (
                session.agenda_item.space.area.venue.event.get_most_liberal_config(
                    session
                )
            )
            if enrollment_config and enrollment_config.restrict_to_configured_users:
                if not request.di.uow.active_users.read(
                    request.context.current_user_slug
                ).email:
                    messages.error(
                        self.request,
                        _("Email address is required for enrollment in this session."),
                    )
                else:
                    user_email = request.di.uow.active_users.read(
                        request.context.current_user_slug
                    ).email
                    event = session.agenda_item.space.area.venue.event
                    if not get_user_enrollment_config(
                        event=EventDTO.model_validate(event),
                        user_email=user_email,
                        enrollment_config_repo=request.di.uow.enrollment_configs,
                        ticket_api=request.di.ticket_api,
                        check_interval_minutes=settings.MEMBERSHIP_API_CHECK_INTERVAL,
                    ):
                        messages.error(
                            self.request,
                            _(
                                "Enrollment access permission is required for this "
                                "session. Please contact the organizers to obtain "
                                "access."
                            ),
                        )
                    else:
                        messages.warning(
                            self.request,
                            _("Please review the enrollment options below."),
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
                    "event": session.agenda_item.space.area.venue.event,
                    "connected_users": self.request.di.uow.connected_users.read_all(
                        self.request.context.current_user_slug
                    ),
                    "user_data": self._get_user_participation_data(session),
                    "form": form,
                },
            )

        # Only validate enrollment requirements when form is valid
        enrollment_config = self._validate_request(session)

        self._manage_enrollments(form, session, enrollment_config)

        return redirect(
            "web:chronology:event", slug=session.agenda_item.space.area.venue.event.slug
        )

    def _get_enrollment_requests(self, form: forms.Form) -> list[EnrollmentRequest]:
        enrollment_requests = []
        for user in (
            self.request.di.uow.active_users.read(
                self.request.context.current_user_slug
            ),
            *self.request.di.uow.connected_users.read_all(
                self.request.context.current_user_slug
            ),
        ):
            # Skip inactive users
            if not user.is_active:
                continue
            user_field = f"user_{user.pk}"
            if form.cleaned_data.get(user_field):
                choice = form.cleaned_data[user_field]
                enrollment_requests.append(
                    EnrollmentRequest(
                        user=user, choice=EnrollmentChoice(choice), name=user.full_name
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

    def _promote_from_waitlist(
        self,
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

                        event = session.agenda_item.space.area.venue.event
                        user_config = get_user_enrollment_config(
                            event=EventDTO.model_validate(event),
                            user_email=manager_user.email,
                            enrollment_config_repo=self.request.di.uow.enrollment_configs,
                            ticket_api=self.request.di.ticket_api,
                            check_interval_minutes=settings.MEMBERSHIP_API_CHECK_INTERVAL,
                        )
                        if user_config and not can_enroll_users(
                            users=[
                                UserDTO.model_validate(manager_user),
                                *[
                                    UserDTO.model_validate(c)
                                    for c in manager_user.connected.all()
                                ],
                            ],
                            event=EventDTO.model_validate(event),
                            virtual_config=user_config,
                            users_to_enroll=[
                                UserDTO.model_validate(participation.user)
                            ],
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
        participation = SessionParticipation.objects.filter(
            session=session, user_id=req.user.pk
        ).first()

        if not participation:
            participation = SessionParticipation(session=session, user_id=req.user.pk)

        participation.status = _status_by_choice[req.choice]
        participation.save()

        enrollments.users_by_status[_status_by_choice[req.choice]].append(req.name)

    def _send_message(self, enrollments: Enrollments) -> None:
        for users, message in (
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
        ):
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
    request: AuthenticatedRootRequest

    def get(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        event = self._validate_event(event_slug)

        proposal_category = self._get_proposal_category(event)
        tag_categories = proposal_category.tag_categories.all()

        return TemplateResponse(
            request,
            "chronology/propose_session.html",
            {
                "event": event,
                "time_slot": None,
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
        self, request: AuthenticatedRootRequest, event_slug: str  # noqa: ARG002
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
                    "time_slot": None,
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
            host_id=self.request.context.current_user_id,
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
                sphere_id=self.request.context.current_sphere_id, slug=event_slug
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


class ProposalAcceptPageView(LoginRequiredMixin, View):
    def get(self, request: AuthenticatedRootRequest, proposal_id: int) -> HttpResponse:
        proposal_repository = request.di.uow.proposals
        try:
            proposal = proposal_repository.read(proposal_id)
        except NotFoundError as exception:
            raise RedirectError(
                reverse("web:index"), error=_("Proposal not found.")
            ) from exception

        event = proposal_repository.read_event(proposal.pk)
        # Check if proposal is already accepted
        if proposal.session_id:
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event.slug}),
                warning=_("This proposal has already been accepted."),
            )

        service = AcceptProposalService(request.di.uow, context=request.context)
        # Check permissions
        if not service.can_accept_proposals():
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event.slug}),
                error=_(
                    "You don't have permission to accept proposals for this event."
                ),
            )

        # Get available spaces and time slots for the event
        self._check_spaces(proposal, proposal_repository)
        self._check_time_slots(proposal, proposal_repository)

        # Create the form
        form_class = create_proposal_acceptance_form(event)
        form = form_class()

        tags = proposal_repository.read_tags(proposal.pk)
        tag_categories = {
            tc.pk: tc for tc in proposal_repository.read_tag_categories(proposal.pk)
        }

        context = {
            "proposal": proposal,
            "host": proposal_repository.read_host(proposal.pk),
            "event": event,
            "spaces": proposal_repository.read_spaces(proposal.pk),
            "time_slots": proposal_repository.read_time_slots(proposal.pk),
            "form": form,
            "proposal_host": proposal_repository.read_host(proposal.pk),
            "tags": [
                {"category_icon": tag_categories[tag.category_id], "name": tag.name}
                for tag in tags
            ],
        }

        return TemplateResponse(request, "chronology/accept_proposal.html", context)

    def post(self, request: AuthenticatedRootRequest, proposal_id: int) -> HttpResponse:
        proposal_repository = request.di.uow.proposals
        try:
            proposal = proposal_repository.read(proposal_id)
        except NotFoundError as exception:
            raise RedirectError(
                reverse("web:index"), error=_("Proposal not found.")
            ) from exception

        event = proposal_repository.read_event(proposal.pk)
        # Check if proposal is already accepted
        if proposal.session_id:
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event.slug}),
                warning=_("This proposal has already been accepted."),
            )

        service = AcceptProposalService(request.di.uow, context=request.context)
        # Check permissions
        if not service.can_accept_proposals():
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event.slug}),
                error=_(
                    "You don't have permission to accept proposals for this event."
                ),
            )

        # Initialize form with POST data
        form_class = create_proposal_acceptance_form(event)
        form = form_class(data=request.POST)
        if not form.is_valid():
            # Re-render with form errors
            tags = proposal_repository.read_tags(proposal.pk)
            tag_categories = {
                tc.pk: tc for tc in proposal_repository.read_tag_categories(proposal.pk)
            }

            return TemplateResponse(
                request,
                "chronology/accept_proposal.html",
                {
                    "proposal": proposal,
                    "host": proposal_repository.read_host(proposal.pk),
                    "event": event,
                    "spaces": proposal_repository.read_spaces(proposal.pk),
                    "time_slots": proposal_repository.read_time_slots(proposal.pk),
                    "form": form,
                    "proposal_host": proposal_repository.read_host(proposal.pk),
                    "tags": [
                        {
                            "category_icon": tag_categories[tag.category_id],
                            "name": tag.name,
                        }
                        for tag in tags
                    ],
                },
            )

        service.accept_proposal(
            proposal=proposal,
            slugifier=slugify,
            space_id=form.cleaned_data["space"].id,
            time_slot_id=form.cleaned_data["time_slot"].id,
        )

        messages.success(
            self.request,
            _("Proposal '{}' has been accepted and added to the agenda.").format(
                proposal.title
            ),
        )
        return redirect("web:chronology:event", slug=event.slug)

    @staticmethod
    def _check_spaces(
        proposal: ProposalDTO, proposal_repository: ProposalRepositoryProtocol
    ) -> None:
        if not proposal_repository.read_spaces(proposal.pk):
            raise RedirectError(
                reverse(
                    "web:chronology:event",
                    kwargs={"slug": proposal_repository.read_event(proposal.pk).slug},
                ),
                error=_(
                    "No spaces configured for this event. Please create spaces first."
                ),
            )

    @staticmethod
    def _check_time_slots(
        proposal: ProposalDTO, proposal_repository: ProposalRepositoryProtocol
    ) -> None:
        if not proposal_repository.read_time_slots(proposal.pk):
            raise RedirectError(
                reverse(
                    "web:chronology:event",
                    kwargs={"slug": proposal_repository.read_event(proposal.pk).slug},
                ),
                error=_(
                    "No time slots configured for this event. "
                    "Please create time slots first."
                ),
            )


class EventAnonymousActivateActionView(View):
    @staticmethod
    def get(request: RootRequest, event_slug: str) -> HttpResponse:
        # Redirect to event page if user is authenticated (not anonymous)
        if request.context.current_user_slug:
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
        user_repository = request.di.uow.anonymous_users
        service = AnonymousEnrollmentService(user_repository=user_repository)
        user = service.build_user(code)
        user_repository.create(user)

        # Set session flags - include site ID to prevent cross-site confusion
        request.session["anonymous_user_code"] = code
        request.session["anonymous_enrollment_active"] = True
        request.session["anonymous_event_id"] = event.id
        request.session["anonymous_site_id"] = request.context.current_site_id

        return redirect("web:chronology:event", slug=event.slug)


class SessionEnrollmentAnonymousPageView(View):
    @staticmethod
    def get(request: RootRequest, session_id: int) -> HttpResponse:
        # Redirect to regular enrollment if user is authenticated
        if request.context.current_user_slug:
            return redirect("web:chronology:session-enrollment", session_id=session_id)

        # Check if anonymous mode is active
        if not request.session.get("anonymous_enrollment_active"):
            messages.error(request, _("Anonymous enrollment is not active."))
            return redirect("web:index")

        # Check if anonymous user is for the current site
        current_site_id = request.context.current_site_id
        session_site_id = request.session.get("anonymous_site_id")
        if session_site_id != current_site_id:
            messages.error(
                request, _("Anonymous enrollment session is not valid for this site.")
            )
            return redirect("web:index")

        # Get session
        try:
            session = Session.objects.get(
                id=session_id, sphere__site_id=request.context.current_site_id
            )
        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")

        # Get anonymous user from session
        if not (anonymous_user_code := request.session.get("anonymous_user_code")):
            messages.error(request, _("Anonymous session expired."))
            return redirect("web:index")

        user_repository = request.di.uow.anonymous_users
        service = AnonymousEnrollmentService(user_repository=user_repository)
        # Look up user by code
        try:
            anonymous_user = service.get_user_by_code(code=anonymous_user_code)
        except NotFoundError:
            messages.error(request, _("Anonymous user not found."))
            return redirect("web:index")

        # Check if user is already enrolled in THIS specific session
        existing_enrollment = SessionParticipation.objects.filter(
            session=session, user_id=anonymous_user.pk
        ).first()

        context = {
            "session": session,
            "event": session.agenda_item.space.area.venue.event,
            "anonymous_user": anonymous_user,
            "anonymous_code": anonymous_user.slug.removeprefix("code_"),
            "needs_user_data": not anonymous_user.name,
            "existing_enrollment": existing_enrollment,
            "is_enrolled": existing_enrollment is not None,
        }

        return TemplateResponse(request, "chronology/anonymous_enroll.html", context)

    @staticmethod
    def post(request: RootRequest, session_id: int) -> HttpResponse:
        # Redirect to regular enrollment if user is authenticated
        if request.context.current_user_slug:
            return redirect("web:chronology:session-enrollment", session_id=session_id)

        # Check if anonymous mode is active
        if not request.session.get("anonymous_enrollment_active"):
            messages.error(request, _("Anonymous enrollment is not active."))
            return redirect("web:index")

        # Check if anonymous user is for the current site
        current_site_id = request.context.current_site_id
        session_site_id = request.session.get("anonymous_site_id")
        if session_site_id != current_site_id:
            messages.error(
                request, _("Anonymous enrollment session is not valid for this site.")
            )
            return redirect("web:index")

        # Get session
        try:
            session = Session.objects.get(
                id=session_id, sphere__site_id=request.context.current_site_id
            )
        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")

        # Get anonymous user
        if not (anonymous_user_code := request.session.get("anonymous_user_code")):
            messages.error(request, _("Anonymous session expired."))
            return redirect("web:index")

        user_repository = request.di.uow.anonymous_users
        service = AnonymousEnrollmentService(user_repository=user_repository)
        # Look up user by code
        try:
            anonymous_user = service.get_user_by_code(code=anonymous_user_code)
        except NotFoundError:
            messages.error(request, _("Anonymous user not found."))
            return redirect("web:index")

        # Update user data if provided
        if name := request.POST.get("name", "").strip():
            anonymous_user.name = name

        # Validate required fields
        if not anonymous_user.name:
            messages.error(request, _("Name is required."))
            return redirect(
                "web:chronology:session-enrollment-anonymous", session_id=session_id
            )

        user_repository.update(anonymous_user.slug, UserData(name=name))

        # Check for cancellation request
        if request.POST.get("action", "enroll") == "cancel":
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
            "web:chronology:event", slug=session.agenda_item.space.area.venue.event.slug
        )


class AnonymousLoadActionView(View):
    """Handle entering an anonymous code to load a previous session."""

    @staticmethod
    def post(request: RootRequest) -> HttpResponse:
        # Only accessible to non-authenticated users
        if request.context.current_user_slug:
            return redirect("web:index")

        if not (code := request.POST.get("code", "").strip()):
            messages.error(request, _("Please enter a code."))
            # Try to redirect back to the referring event
            referer = request.META.get("HTTP_REFERER", "")
            if "event" in referer:
                return redirect(referer)
            return redirect("web:index")

        user_repository = request.di.uow.anonymous_users
        service = AnonymousEnrollmentService(user_repository=user_repository)
        # Look up user by code
        try:
            anonymous_user = service.get_user_by_code(code=code)
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
        ).select_related(
            "session__agenda_item__space__area__venue__event", "session__sphere"
        )

        if not (first_enrollment := enrollments.first()):
            messages.warning(request, _("No enrollments found for this code."))
            return redirect("web:index")

        # Get the first enrollment to determine the event and site
        event = first_enrollment.session.agenda_item.space.area.venue.event
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
