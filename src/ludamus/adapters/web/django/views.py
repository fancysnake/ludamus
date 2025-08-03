import json
from collections import defaultdict
from collections.abc import Generator
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any, TypedDict
from urllib.parse import quote_plus, urlencode, urlparse

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.core.cache import cache
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic.base import RedirectView, View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from ludamus.adapters.db.django.models import (
    MAX_CONNECTED_USERS,
    AgendaItem,
    Event,
    Proposal,
    ProposalCategory,
    Session,
    SessionParticipation,
    SessionParticipationStatus,
    Space,
    Sphere,
    Tag,
    TimeSlot,
)
from ludamus.adapters.oauth import oauth
from ludamus.adapters.web.django.entities import (
    SessionData,
    SessionUserParticipationData,
)

from .exceptions import RedirectError
from .forms import (
    EnrollmentForm,
    ProposalAcceptanceForm,
    SessionProposalForm,
    ThemeSelectionForm,
)

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User
else:
    User = get_user_model()


TODAY = datetime.now(tz=UTC).date()
MINIMUM_ALLOWED_USER_AGE = 16
CACHE_TIMEOUT = 600  # 10 minutes


class WrongSiteTypeError(TypeError):
    def __init__(self) -> None:
        super().__init__(_("Wrong type of site!"))


def get_site_from_request(request: HttpRequest | None) -> Site:
    site = get_current_site(request)
    if isinstance(site, Site):
        return site

    raise WrongSiteTypeError


class UserRequest(HttpRequest):
    user: User
    sphere: Sphere | None


def login(request: HttpRequest) -> HttpResponse:
    """Display login required page instead of immediate redirect to Auth0.

    Returns:
        TemplateResponse: The login required page.
    """
    next_url = request.GET.get("next", "")
    context = {"next": next_url}
    return TemplateResponse(request, "crowd/user/login_required.html", context)


def auth0_login(request: HttpRequest) -> HttpResponse:
    """Redirect to Auth0 for authentication.

    Returns:
        HttpResponse: Redirect to Auth0 authorization endpoint.

    Raises:
        RedirectError: If the request is not from the root domain.
    """
    root_domain = Site.objects.get(domain=settings.ROOT_DOMAIN).domain
    next_path = request.GET.get("next")
    if request.get_host() != root_domain:
        url = f'{request.scheme}://{root_domain}{reverse("web:auth0_login")}?next={next_path}'
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
        request, request.build_absolute_uri(reverse("web:callback")), state=state_token
    )


class CallbackView(RedirectView):

    def get_redirect_url(  # type: ignore [explicit-any]
        self, *args: Any, **kwargs: Any
    ) -> str | None:
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
        if not self.request.user.is_authenticated:
            username = self._get_username()
            user, created = User.objects.get_or_create(username=username)

            # Check if user is inactive due to being under 16
            if user.birth_date and user.age < MINIMUM_ALLOWED_USER_AGE:
                # Redirect to under-age page without logging them in
                return _auth0_logout_url(
                    self.request, redirect_to=reverse("web:under-age")
                )

            # Log the user in
            django_login(self.request, user)
            messages.success(self.request, _("Welcome!"))

            # Check if profile needs completion
            if created or user.is_incomplete:
                messages.success(self.request, _(" Please complete your profile."))
                if redirect_to:
                    parsed = urlparse(redirect_to)
                    return f'{parsed.scheme}://{parsed.netloc}{reverse("web:edit")}'
                return self.request.build_absolute_uri(reverse("web:edit"))

        return redirect_to or self.request.build_absolute_uri(reverse("web:index"))

    def _get_username(self) -> str:
        token = oauth.auth0.authorize_access_token(self.request)

        try:
            return f'auth0|{token["userinfo"]["sub"].encode("UTF-8")}'
        except (KeyError, TypeError):
            raise RedirectError(
                reverse("web:index"), error=_("Authentication failed")
            ) from None


def logout(request: HttpRequest) -> HttpResponse:
    django_logout(request)

    last_domain = get_site_from_request(request).domain
    messages.success(request, _("You have been successfully logged out."))

    return redirect(_auth0_logout_url(request, last_domain=last_domain))


def _auth0_logout_url(
    request: HttpRequest,
    *,
    last_domain: str | None = None,
    redirect_to: str | None = None,
) -> str:
    root_domain = Site.objects.get(domain=settings.ROOT_DOMAIN).domain
    last_domain = last_domain or root_domain
    redirect_to = redirect_to or reverse("web:index")
    return f"https://{settings.AUTH0_DOMAIN}/v2/logout?" + urlencode(
        {
            "returnTo": (
                f'{request.scheme}://{root_domain}{reverse("web:redirect")}?last_domain={last_domain}&redirect_to={redirect_to}'
            ),
            "client_id": settings.AUTH0_CLIENT_ID,
        },
        quote_via=quote_plus,
    )


def redirect_view(request: HttpRequest) -> HttpResponse:
    redirect_url = reverse("web:index")

    # Get the redirect_to parameter
    if redirect_to := request.GET.get("redirect_to"):
        # Only allow relative URLs (starting with /)
        if redirect_to.startswith("/") and not redirect_to.startswith("//"):
            redirect_url = redirect_to
        else:
            messages.warning(request, _("Invalid redirect URL."))

    # Handle last_domain parameter for multi-site redirects
    if last_domain := request.GET.get("last_domain"):
        # Validate that the domain belongs to a known site
        allowed_domains = list(Site.objects.values_list("domain", flat=True))

        # Also allow subdomains of ROOT_DOMAIN if configured
        if hasattr(settings, "ROOT_DOMAIN") and (
            last_domain.endswith(f".{settings.ROOT_DOMAIN}")
            or last_domain == settings.ROOT_DOMAIN
        ):
            return redirect(f"{request.scheme}://{last_domain}{redirect_url}")

        # Check against explicitly allowed domains
        if last_domain in allowed_domains:
            return redirect(f"{request.scheme}://{last_domain}{redirect_url}")

        messages.warning(request, _("Invalid domain for redirect."))

    return redirect(redirect_url)


def index(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(
        request,
        "index.html",
        context={
            "events": list(
                Event.objects.filter(sphere__site=get_site_from_request(request)).all()
            )
        },
    )


def under_age(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(request, "crowd/user/under_age.html")


class BaseUserForm(forms.ModelForm):  # type: ignore [type-arg]
    name = forms.CharField(label=_("User name"), required=True)
    birth_date = forms.DateField(
        label=_("Birth date"),
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
                "max": TODAY,
                "min": TODAY - timedelta(days=100 * 365.25),
            },
            format="%Y-%m-%d",
        ),
    )

    class Meta:
        model = User
        fields = ("name", "birth_date", "user_type")


class UserForm(BaseUserForm):
    user_type = forms.CharField(
        initial=User.UserType.ACTIVE, widget=forms.HiddenInput()
    )

    class Meta:
        model = User
        fields = ("name", "email", "birth_date", "user_type")


class ConnectedUserForm(BaseUserForm):
    user_type = forms.CharField(
        initial=User.UserType.CONNECTED.value, widget=forms.HiddenInput()
    )


class EditProfileView(LoginRequiredMixin, UpdateView):  # type: ignore [type-arg]
    template_name = "crowd/user/edit.html"
    form_class = UserForm
    success_url = reverse_lazy("web:index")
    request: UserRequest

    def get_object(
        self, queryset: QuerySet[User] | None = None  # noqa: ARG002
    ) -> User:
        return self.request.user

    def form_valid(self, form: UserForm) -> HttpResponse:
        user = form.save(commit=False)

        # Check if user is under 16
        if user.birth_date and user.age < MINIMUM_ALLOWED_USER_AGE:
            user.is_active = False
            user.save()
            django_logout(self.request)
            return redirect(
                _auth0_logout_url(self.request, redirect_to=reverse("web:under-age"))
            )

        user.save()
        messages.success(self.request, _("Profile updated successfully!"))
        return super().form_valid(form)

    def form_invalid(self, form: forms.Form) -> HttpResponse:
        messages.warning(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


class ConnectedView(LoginRequiredMixin, CreateView):  # type: ignore [type-arg]
    template_name = "crowd/user/connected.html"
    form_class = ConnectedUserForm
    success_url = reverse_lazy("web:connected")
    request: UserRequest
    object: User

    def get_context_data(  # type: ignore [explicit-any]
        self, **kwargs: Any
    ) -> dict[str, Any]:

        context = super().get_context_data(**kwargs)
        connected_users = [
            {"user": connected, "form": ConnectedUserForm(instance=connected)}
            for connected in self.request.user.connected.all()
        ]
        context["connected_users"] = connected_users
        context["max_connected_users"] = MAX_CONNECTED_USERS
        return context

    def form_valid(self, form: forms.Form) -> HttpResponse:
        # Check if user has reached the maximum number of connected users

        connected_count = self.request.user.connected.count()
        if connected_count >= MAX_CONNECTED_USERS:
            messages.error(
                self.request,
                _("You can only have up to %(max)s connected users.")
                % {"max": MAX_CONNECTED_USERS},
            )
            return self.form_invalid(form)

        result = super().form_valid(form)
        self.object.manager = self.request.user
        self.object.username = f"connected|{token_urlsafe(50)}"
        self.object.save()
        messages.success(self.request, _("Connected user added successfully!"))
        return result

    def form_invalid(self, form: forms.Form) -> HttpResponse:
        messages.warning(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


class EditConnectedView(LoginRequiredMixin, UpdateView):  # type: ignore [type-arg]
    template_name = "crowd/user/connected.html"
    form_class = ConnectedUserForm
    success_url = reverse_lazy("web:connected")
    model = User
    request: UserRequest

    def get_queryset(self) -> QuerySet[User]:
        return User.objects.filter(
            manager=self.request.user, user_type=User.UserType.CONNECTED
        )

    def form_valid(self, form: forms.Form) -> HttpResponse:
        messages.success(self.request, _("Connected user updated successfully!"))
        return super().form_valid(form)

    def form_invalid(self, form: forms.Form) -> HttpResponse:
        messages.warning(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


class DeleteConnectedView(LoginRequiredMixin, DeleteView):  # type: ignore [type-arg]
    model = User
    success_url = reverse_lazy("web:connected")
    request: UserRequest

    def get_queryset(self) -> QuerySet[User]:
        return User.objects.filter(
            manager=self.request.user, user_type=User.UserType.CONNECTED
        )

    def form_valid(self, form: forms.Form) -> HttpResponse:
        messages.success(self.request, _("Connected user deleted successfully."))
        return super().form_valid(form)


class HourData(TypedDict):
    time_slot: TimeSlot
    sessions: list[SessionData]


class EventView(DetailView):  # type: ignore [type-arg]
    template_name = "chronology/event.html"
    model = Event
    context_object_name = "event"
    request: UserRequest

    def get_queryset(self) -> QuerySet[Event]:
        return (
            Event.objects.filter(sphere=self.request.sphere)
            .select_related("sphere")
            .prefetch_related("spaces__agenda_items__session")
        )

    def get_context_data(  # type: ignore [explicit-any]
        self, **kwargs: Any
    ) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        # Get all sessions for this event that are published
        event_sessions = (
            Session.objects.filter(agenda_item__space__event=self.object)
            .select_related("host", "agenda_item__space")
            .prefetch_related("tags", "session_participations__user")
            .order_by("agenda_item__start_time")
        )

        hour_data = dict(self._get_hour_data(event_sessions))
        context.update({"hour_data": hour_data, "sessions": list(event_sessions)})

        # Add proposals for superusers
        if self.request.user.is_superuser:
            context["proposals"] = list(
                Proposal.objects.filter(
                    category__event=self.object,
                    session__isnull=True,  # Only unaccepted proposals
                )
                .select_related("host", "category")
                .prefetch_related("tags", "time_slots")
                .order_by("-creation_time")
            )

        return context

    def _set_user_participations(
        self, sessions: dict[int, SessionData], event_sessions: QuerySet[Session]
    ) -> None:
        participations = SessionParticipation.objects.filter(session__in=event_sessions)
        # Add user participation info for each session
        for user in [self.request.user, *self.request.user.connected.all()]:
            for session in event_sessions:
                statuses = {
                    p.status
                    for p in participations
                    if p.user == user and p.session == session
                }

                sessions[session.id].has_any_enrollments |= bool(statuses)
                sessions[session.id].user_enrolled |= (
                    SessionParticipationStatus.CONFIRMED in statuses
                )
                sessions[session.id].user_waiting |= (
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

        if self.request.user.is_authenticated:
            self._set_user_participations(sessions_data, event_sessions)

        return sessions_data


class EnrollmentChoice(StrEnum):
    CANCEL = auto()
    ENROLL = auto()
    WAITLIST = auto()


@dataclass
class EnrollmentRequest:
    user: User
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


def _get_session_or_redirect(request: UserRequest, session_id: int) -> Session:
    try:
        return Session.objects.get(sphere=request.sphere, id=session_id)
    except Session.DoesNotExist:
        raise RedirectError(
            reverse("web:index"), error=_("Session not found.")
        ) from None


_status_by_choice = {
    "enroll": SessionParticipationStatus.CONFIRMED,
    "waitlist": SessionParticipationStatus.WAITING,
}


class EnrollSelectView(LoginRequiredMixin, View):
    request: UserRequest

    def get(self, request: UserRequest, session_id: int) -> HttpResponse:
        session = _get_session_or_redirect(request, session_id)

        context = {
            "session": session,
            "event": session.agenda_item.space.event,
            "connected_users": list(self.request.user.connected.all()),
            "user_data": self._get_user_participation_data(session),
            "form": EnrollmentForm(
                session=session,
                users=[self.request.user, *request.user.connected.all()],
            ),
        }

        return TemplateResponse(request, "chronology/enroll_select.html", context)

    def _validate_request(self, session: Session) -> None:
        # Check if user has birth date set
        if not self.request.user.birth_date:
            raise RedirectError(
                reverse("web:edit"),
                error=_(
                    "Please complete your profile with birth date before enrolling."
                ),
            )

        # Check if enrollment is active for the event
        if not session.agenda_item.space.event.is_enrollment_active:
            raise RedirectError(
                reverse(
                    "web:event", kwargs={"slug": session.agenda_item.space.event.slug}
                ),
                error=_("Enrollment is not currently active for this event."),
            )

    def _get_user_participation_data(
        self, session: Session
    ) -> list[SessionUserParticipationData]:
        user_data: list[SessionUserParticipationData] = []

        # Add enrollment status and time conflict info for each connected user
        for user in [self.request.user, *self.request.user.connected.all()]:
            # Include all users in display but mark inactive ones
            user_participations = SessionParticipation.objects.filter(
                user=user,
                session__agenda_item__space__event=session.agenda_item.space.event,
            )
            data = SessionUserParticipationData(
                user=user,
                user_enrolled=user_participations.filter(
                    status=SessionParticipationStatus.CONFIRMED
                ).exists(),
                user_waiting=user_participations.filter(
                    status=SessionParticipationStatus.WAITING
                ).exists(),
                has_time_conflict=any(
                    s
                    for s in user_participations.exclude(
                        session=session, status=SessionParticipationStatus.CONFIRMED
                    )
                    if session.agenda_item.overlaps_with(s.session.agenda_item)
                ),
            )
            user_data.append(data)

        return user_data

    def post(self, request: UserRequest, session_id: int) -> HttpResponse:
        session = _get_session_or_redirect(request, session_id)

        self._validate_request(session)

        # Initialize form with POST data
        form = EnrollmentForm(
            data=request.POST,
            session=session,
            users=[self.request.user, *request.user.connected.all()],
        )

        if not form.is_valid():
            messages.warning(self.request, _("Please correct the errors below."))
            # Re-render with form errors
            return TemplateResponse(
                request,
                "chronology/enroll_select.html",
                {
                    "session": session,
                    "event": session.agenda_item.space.event,
                    "connected_users": list(self.request.user.connected.all()),
                    "user_data": self._get_user_participation_data(session),
                    "form": form,
                },
            )

        self._manage_enrollments(form, session)

        return redirect("web:event", slug=session.agenda_item.space.event.slug)

    def _get_enrollment_requests(self, form: EnrollmentForm) -> list[EnrollmentRequest]:
        enrollment_requests = []
        for connected_user in [self.request.user, *self.request.user.connected.all()]:
            # Skip inactive users
            if not connected_user.is_active:
                continue
            user_field = f"user_{connected_user.id}"
            if form.cleaned_data.get(user_field):
                choice = form.cleaned_data[user_field]
                enrollment_requests.append(
                    EnrollmentRequest(
                        user=connected_user,
                        choice=EnrollmentChoice(choice),
                        name=connected_user.get_full_name(),
                    )
                )
        return enrollment_requests

    def _process_enrollments(
        self, enrollment_requests: list[EnrollmentRequest], session: Session
    ) -> Enrollments:
        enrollments = Enrollments()
        participations = SessionParticipation.objects.filter(session=session).order_by(
            "creation_time"
        )

        for req in enrollment_requests:
            # Handle cancellation
            if req.choice == "cancel":
                self._handle_cancellation(participations, req, enrollments, session)
                continue

            self._check_and_create_enrollment(req, session, enrollments)
        return enrollments

    def _handle_cancellation(
        self,
        participations: QuerySet[SessionParticipation],
        req: EnrollmentRequest,
        enrollments: Enrollments,
        session: Session,
    ) -> None:
        if existing_participation := next(
            p for p in participations if p.user == req.user
        ):
            existing_participation.delete()
            enrollments.cancelled_users.append(req.name)

            # If this was a confirmed enrollment, promote from waiting list
            self._promote_from_waitlist(
                existing_participation, participations, req, session, enrollments
            )
        else:
            enrollments.skipped_users.append(f"{req.name} ({_('not enrolled')!s})")

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
                    participation.user != req.user
                    and participation.status == SessionParticipationStatus.WAITING
                ) and not Session.objects.has_conflicts(session, participation.user):
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
        # Check if user is the session host
        if req.user == session.host:
            enrollments.skipped_users.append(f"{req.name} ({_('session host')!s})")
            return
        # Check if user is already enrolled
        if SessionParticipation.objects.filter(session=session, user=req.user).exists():
            enrollments.skipped_users.append(f"{req.name} ({_('already enrolled')!s})")
            return
        # Check for time conflicts for confirmed enrollment
        if req.choice == "enroll" and Session.objects.has_conflicts(session, req.user):
            enrollments.skipped_users.append(f"{req.name} ({_('time conflict')!s})")
            return

        # Create enrollment
        SessionParticipation.objects.create(
            session=session, user=req.user, status=_status_by_choice[req.choice]
        )
        enrollments.users_by_status[_status_by_choice[req.choice]].append(req.name)

    def _send_message(self, enrollments: Enrollments) -> None:
        any_users = False
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
                any_users = True
                messages.success(self.request, message.format(", ".join(users)))

        if not any_users:
            messages.warning(self.request, _("No enrollments were processed."))

    def _is_capacity_invalid(
        self, enrollment_requests: list[EnrollmentRequest], session: Session
    ) -> bool:
        confirmed_requests = [
            req for req in enrollment_requests if req.choice == "enroll"
        ]
        current_confirmed = session.session_participations.filter(
            status=SessionParticipationStatus.CONFIRMED
        ).count()
        available_spots = session.participants_limit - current_confirmed

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

    def _manage_enrollments(self, form: EnrollmentForm, session: Session) -> None:
        # Collect enrollment requests from form
        if enrollment_requests := self._get_enrollment_requests(form):
            # Validate capacity for confirmed enrollments
            if self._is_capacity_invalid(enrollment_requests, session):
                raise RedirectError(
                    reverse("web:enroll-select", kwargs={"session_id": session.id})
                )

            # Process enrollments and create success message
            self._send_message(self._process_enrollments(enrollment_requests, session))
        else:
            raise RedirectError(
                reverse("web:enroll-select", kwargs={"session_id": session.id}),
                warning=_("Please select at least one user to enroll."),
            )


class ProposeSessionView(LoginRequiredMixin, View):
    request: UserRequest

    def get(self, request: UserRequest, event_slug: str) -> HttpResponse:
        event = self._validate_event(event_slug)

        # Check if user has birth date set
        if not request.user.birth_date:
            raise RedirectError(
                reverse("web:edit"),
                error=_(
                    "Please complete your profile with birth date before "
                    "submitting proposals."
                ),
            )

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
                "form": SessionProposalForm(
                    proposal_category=proposal_category,
                    initial={
                        "participants_limit": proposal_category.min_participants_limit
                    },
                ),
            },
        )

    def post(self, request: UserRequest, event_slug: str) -> HttpResponse:
        event = self._validate_event(event_slug)

        # Check if user has birth date set
        if not request.user.birth_date:
            raise RedirectError(
                reverse("web:edit"),
                error=_(
                    "Please complete your profile with birth date before "
                    "submitting proposals."
                ),
            )

        proposal_category = self._get_proposal_category(event)

        return self._handle_form(proposal_category, event)

    def _handle_form(
        self, proposal_category: ProposalCategory, event: Event
    ) -> HttpResponse:
        # Initialize form with POST data
        form = SessionProposalForm(
            data=self.request.POST, proposal_category=proposal_category
        )

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
            host=self.request.user,
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            requirements=form.cleaned_data["requirements"],
            needs=form.cleaned_data["needs"],
            participants_limit=form.cleaned_data["participants_limit"],
        )

        for tag in self._get_tags(form.get_tag_data(), proposal_category):
            proposal.tags.add(tag)

        messages.success(
            self.request,
            _("Session proposal '{}' submitted successfully!").format(
                form.cleaned_data["title"]
            ),
        )
        return redirect("web:event", slug=event.slug)

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
            event = Event.objects.get(sphere=self.request.sphere, slug=event_slug)
        except Event.DoesNotExist:
            raise RedirectError(
                reverse("web:index"), error=_("Event not found.")
            ) from None

        if not event.is_proposal_active:
            raise RedirectError(
                reverse("web:event", kwargs={"slug": event_slug}),
                error=_("Proposal submission is not currently active for this event."),
            )

        return event

    @staticmethod
    def _get_proposal_category(event: Event) -> ProposalCategory:
        try:
            return ProposalCategory.objects.get(event=event)
        except ProposalCategory.DoesNotExist:
            raise RedirectError(
                reverse("web:event", kwargs={"slug": event.slug}),
                error=_(
                    "No proposal category configured for this event. "
                    "Please contact the organizers."
                ),
            ) from None


def _get_proposal(request: UserRequest, proposal_id: int) -> Proposal:
    try:
        proposal = Proposal.objects.get(
            category__event__sphere=request.sphere, id=proposal_id
        )
    except Proposal.DoesNotExist:
        raise RedirectError(
            reverse("web:index"), error=_("Proposal not found.")
        ) from None

    # Check if proposal is already accepted
    if proposal.session:
        raise RedirectError(
            reverse("web:event", kwargs={"slug": proposal.category.event.slug}),
            warning=_("This proposal has already been accepted."),
        )

    return proposal


@method_decorator(staff_member_required, name="dispatch")
class AcceptProposalPageView(LoginRequiredMixin, View):
    def get(self, request: UserRequest, proposal_id: int) -> HttpResponse:
        proposal = _get_proposal(request, proposal_id)
        event = proposal.category.event

        # Get available spaces and time slots for the event
        spaces = self._get_spaces(event)
        time_slots = self._get_time_slots(event)

        # Create the form
        form = ProposalAcceptanceForm(event=event)

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
                reverse("web:event", kwargs={"slug": event.slug}),
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
                reverse("web:event", kwargs={"slug": event.slug}),
                error=_(
                    "No time slots configured for this event. "
                    "Please create time slots first."
                ),
            )

        return list(time_slots)


@method_decorator(staff_member_required, name="dispatch")
class AcceptProposalView(LoginRequiredMixin, View):
    def post(self, request: UserRequest, proposal_id: int) -> HttpResponse:
        proposal = _get_proposal(request, proposal_id)
        event = proposal.category.event

        # Initialize form with POST data
        form = ProposalAcceptanceForm(data=request.POST, event=event)
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
        return redirect("web:event", slug=event.slug)

    @staticmethod
    def _create_session(form: ProposalAcceptanceForm, proposal: Proposal) -> None:
        time_slot = form.cleaned_data["time_slot"]

        # Create a session from the proposal
        session = Session.objects.create(
            sphere=proposal.category.event.sphere,
            host=proposal.host,
            title=proposal.title,
            description=proposal.description,
            requirements=proposal.requirements,
            participants_limit=proposal.participants_limit,
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


class ThemeSelectionView(View):
    @staticmethod
    def post(request: UserRequest) -> HttpResponse:
        form = ThemeSelectionForm(request.POST)
        if form.is_valid():
            theme = form.cleaned_data["theme"]
            request.session["theme"] = theme
            # Redirect back to the referring page
            return redirect(request.META.get("HTTP_REFERER", "/"))

        # If form is invalid, redirect back anyway
        return redirect(request.META.get("HTTP_REFERER", "/"))
