import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum, auto
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any
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
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic.base import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from ludamus.adapters.db.django.models import (
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

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User
else:
    User = get_user_model()


TODAY = datetime.now(tz=UTC).date()
SEPARATOR = "|"


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
    root_domain = Site.objects.get(domain=settings.ROOT_DOMAIN).domain
    next_path = request.GET.get("next")
    if request.get_host() != root_domain:
        return redirect(
            f'{request.scheme}://{root_domain}{reverse("web:login")}?next={next_path}'
        )

    return oauth.auth0.authorize_redirect(  # type: ignore [no-any-return]
        request,
        request.build_absolute_uri(reverse("web:callback") + f"?next={next_path}"),
    )


def callback(request: HttpRequest) -> HttpResponse:
    token = oauth.auth0.authorize_access_token(request)
    if not isinstance(token.get("userinfo"), dict):
        raise TypeError

    sub = token["userinfo"].get("sub")
    username = f'auth0|{sub.encode("UTF-8")}'
    if not isinstance(token["userinfo"].get("sub"), str) or SEPARATOR not in sub:
        raise TypeError

    next_url = request.GET.get("next")
    if request.user.is_authenticated:
        pass
    elif user := User.objects.filter(username=username).first():
        django_login(request, user)
        messages.success(request, _("Welcome back!"))
    else:
        user = User.objects.create_user(username=username)
        django_login(request, user)
        messages.success(request, _("Welcome! Please complete your profile."))
        if next_url:
            parsed = urlparse(next_url)
            return redirect(f'{parsed.scheme}://{parsed.netloc}{reverse("web:edit")}')
        return redirect(request.build_absolute_uri(reverse("web:edit")))

    return redirect(next_url or request.build_absolute_uri(reverse("web:index")))


def logout(request: HttpRequest) -> HttpResponse:
    django_logout(request)
    root_domain = Site.objects.get(domain=settings.ROOT_DOMAIN).domain
    last = get_site_from_request(request).domain
    return_to = f'{request.scheme}://{root_domain}{reverse("web:redirect")}?last={last}'
    messages.success(request, _("You have been successfully logged out."))

    return redirect(
        f"https://{settings.AUTH0_DOMAIN}/v2/logout?"
        + urlencode(
            {"returnTo": return_to, "client_id": settings.AUTH0_CLIENT_ID},
            quote_via=quote_plus,
        )
    )


def redirect_view(request: HttpRequest) -> HttpResponse:
    redirect_url = reverse("web:index")
    if last := request.GET.get("last"):
        redirect_url = f"{request.scheme}://{last}{redirect_url}"

    return redirect(redirect_url)


def index(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(
        request,
        "index.html",
        context={"pretty": json.dumps(request.session.get("user"), indent=4)},
    )


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

    def clean_birth_date(self) -> date:
        validation_error = "You need to be 16 years old to use this website."
        birth_date = self.cleaned_data["birth_date"]

        if not isinstance(birth_date, date) or birth_date >= datetime.now(
            tz=UTC
        ).date() - timedelta(days=16 * 365):
            raise ValidationError(validation_error)

        return birth_date

    class Meta:
        model = User
        fields = ("name", "email", "birth_date", "user_type")


class ConnectedUserForm(BaseUserForm):
    user_type = forms.CharField(
        initial=User.UserType.CONNECTED.value, widget=forms.HiddenInput()  # type: ignore [misc]
    )


class EditProfileView(LoginRequiredMixin, UpdateView):  # type: ignore [type-arg]
    template_name = "crowd/user/edit.html"
    form_class = UserForm
    success_url = "/"
    request: UserRequest

    def get_object(
        self, queryset: QuerySet[User] | None = None  # noqa: ARG002
    ) -> User:
        if not isinstance(self.request.user, User):
            raise TypeError
        return self.request.user

    def form_valid(self, form: forms.Form) -> HttpResponse:
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
        self, **kwargs: Any  # noqa: ANN401
    ) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        connected_users = [
            {"user": connected, "form": ConnectedUserForm(instance=connected)}
            for connected in self.request.user.connected.all()
        ]
        context["connected_users"] = connected_users
        return context

    def get_queryset(self) -> QuerySet[User]:
        return User.objects.filter(
            user_type=User.UserType.CONNECTED, manager=self.request.user
        )

    def form_valid(self, form: forms.Form) -> HttpResponse:
        result = super().form_valid(form)
        self.object.manager = self.request.user
        self.object.username = f"connected|{token_urlsafe(50)}"
        self.object.password = token_urlsafe(50)
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

    def form_valid(self, form: forms.Form) -> HttpResponse:
        messages.success(self.request, _("Connected user updated successfully!"))
        return super().form_valid(form)

    def form_invalid(self, form: forms.Form) -> HttpResponse:
        messages.warning(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


class DeleteConnectedView(LoginRequiredMixin, DeleteView):  # type: ignore [type-arg]
    model = User
    success_url = reverse_lazy("web:connected")

    def form_valid(self, form: forms.Form) -> HttpResponse:
        messages.success(self.request, _("Connected user deleted successfully."))
        return super().form_valid(form)


@dataclass
class SessionUserParticipationData:
    user: User
    user_enrolled: bool = False
    user_waiting: bool = False
    has_time_conflict: bool = False


@dataclass
class SessionData:
    session: Session
    has_any_enrollments: bool = False
    user_enrolled: bool = False
    user_waiting: bool = False


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

    def get_context_data(  # type: ignore [explicit-any]  # noqa: C901
        self, **kwargs: Any  # noqa: ANN401
    ) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        # Get all sessions for this event that are published
        event_sessions = (
            Session.objects.filter(
                agenda_item__space__event=self.object,
                publication_time__lte=datetime.now(tz=UTC),
            )
            .select_related("host", "agenda_item__space")
            .prefetch_related("tags", "session_participations__user")
            .order_by("start_time")
        )
        sessions = {
            session.id: SessionData(session=session) for session in event_sessions
        }

        # Add user participation info for each session
        if self.request.user.is_authenticated:
            for user in [self.request.user, *self.request.user.connected.all()]:
                user_participations = (
                    SessionParticipation.objects.filter(session__in=event_sessions)
                    .filter(Q(user=user))
                    .select_related("session")
                )

                status_by_session: dict[int, str] = {}
                for participation in user_participations:
                    status_by_session[participation.session.id] = participation.status

                for session in event_sessions:
                    match status_by_session.get(session.id):
                        case SessionParticipationStatus.CONFIRMED:
                            sessions[session.id].has_any_enrollments = True
                            sessions[session.id].user_enrolled = True
                        case SessionParticipationStatus.WAITING:
                            sessions[session.id].has_any_enrollments = True
                            sessions[session.id].user_waiting = True

        # Group sessions by time slots
        time_slots = TimeSlot.objects.filter(event=self.object).order_by("start_time")
        sessions_by_slot: dict[TimeSlot, list[SessionData]] = defaultdict(list)

        for session in event_sessions:
            # Find matching time slot for this session
            for slot in time_slots:
                if (
                    session.start_time
                    and session.end_time
                    and slot.start_time <= session.start_time <= slot.end_time
                ):
                    sessions_by_slot[slot].append(sessions[session.id])
                    break

        # Convert to list of (time_slot, sessions) tuples for template
        time_slot_data = [
            {
                "time_slot": slot,
                "sessions": sessions_by_slot[slot],
                "session_count": len(sessions_by_slot[slot]),
            }
            for slot in time_slots
        ]

        context["time_slot_data"] = time_slot_data
        context["sessions"] = event_sessions  # Keep for backward compatibility

        # Add proposals for superusers
        if self.request.user.is_superuser:
            proposals = (
                Proposal.objects.filter(
                    proposal_category__event=self.object,
                    session__isnull=True,  # Only unaccepted proposals
                )
                .select_related("host", "proposal_category")
                .prefetch_related("tags", "time_slots")
                .order_by("-creation_time")
            )
            context["proposals"] = proposals

        return context


class EnrollmentChoice(StrEnum):
    CANCEL = auto()
    ENROLL = auto()
    WAITLIST = auto()


@dataclass
class EnrollmentRequest:
    user: User
    choice: EnrollmentChoice
    name: str = _("yourself")


class EnrollSelectView(LoginRequiredMixin, View):
    request: UserRequest

    def get(self, request: UserRequest, session_id: int) -> HttpResponse:
        try:
            session = Session.objects.get(sphere=request.sphere, id=session_id)
        except Session.DoesNotExist:
            messages.error(self.request, _("Session not found."))
            return redirect("web:index")

        event = session.agenda_item.space.event

        # Check if user has birth date set
        if not request.user.birth_date:
            messages.error(
                request,
                _("Please complete your profile with birth date before enrolling."),
            )
            return redirect("web:edit")

        # Check if enrollment is active for the event
        if not event.is_enrollment_active:
            messages.error(
                request, _("Enrollment is not currently active for this event.")
            )
            return redirect("web:event", slug=event.slug)

        user_datas: list[SessionUserParticipationData] = []

        # Add enrollment status and time conflict info for each connected user
        for user in [self.request.user, *request.user.connected.all()]:
            data = SessionUserParticipationData(user=user)
            user_datas.append(data)
            user_participation = SessionParticipation.objects.filter(
                session=session, user=user
            ).first()

            data.user_enrolled = (
                user_participation.status == SessionParticipationStatus.CONFIRMED
                if user_participation
                else False
            )
            data.user_waiting = (
                user_participation.status == SessionParticipationStatus.WAITING
                if user_participation
                else False
            )

            # Check for time conflicts
            if session.start_time and session.end_time and not user_participation:
                for other_session in Session.objects.filter(
                    agenda_item__space__event=event,
                    session_participations__user=user,
                    session_participations__status=SessionParticipationStatus.CONFIRMED,
                ).exclude(id=session.id):
                    if session.overlaps_with(other_session):
                        data.has_time_conflict = True

        context = {
            "session": session,
            "event": event,
            "connected_users": self.request.user.connected.all(),
            "user_datas": user_datas,
        }

        return TemplateResponse(request, "chronology/enroll_select.html", context)

    def post(  # noqa: PLR0914, PLR0915, PLR0912, C901
        self, request: UserRequest, session_id: int
    ) -> HttpResponse:
        try:
            session = Session.objects.get(sphere=request.sphere, id=session_id)
        except Session.DoesNotExist:
            messages.error(self.request, _("Session not found."))
            return redirect("web:index")

        event = session.agenda_item.space.event

        # Check if user has birth date set
        if not request.user.birth_date:
            messages.error(
                request,
                _("Please complete your profile with birth date before enrolling."),
            )
            return redirect("web:edit")

        # Check if enrollment is active for the event
        if not event.is_enrollment_active:
            messages.error(
                request, _("Enrollment is not currently active for this event.")
            )
            return redirect("web:event", slug=event.slug)

        # Collect enrollment requests from form
        enrollment_requests = []

        # Check for users selections
        for connected_user in [self.request.user, *request.user.connected.all()]:
            if (
                choice := request.POST.get(f"user_{connected_user.id}")
            ) and choice in EnrollmentChoice:
                enrollment_requests.extend(
                    [
                        EnrollmentRequest(
                            user=connected_user,
                            choice=EnrollmentChoice(choice),
                            name=connected_user.get_full_name(),
                        )
                    ]
                )

        if not enrollment_requests:
            messages.warning(request, _("Please select at least one user to enroll."))
            return redirect("web:enroll-select", session_id=session_id)

        # Validate capacity for confirmed enrollments
        confirmed_requests = [
            req for req in enrollment_requests if req.choice == "enroll"
        ]
        current_confirmed = session.session_participations.filter(
            status=SessionParticipationStatus.CONFIRMED
        ).count()
        available_spots = session.participants_limit - current_confirmed

        if len(confirmed_requests) > available_spots:
            messages.error(
                request,
                str(
                    _(
                        "Not enough spots available. {} spots requested, {} available. "
                        "Please use waiting list for some users."
                    )
                ).format(len(confirmed_requests), available_spots),
            )
            return redirect("web:enroll-select", session_id=session_id)

        # Process enrollments
        enrolled_users = []
        waitlisted_users = []
        cancelled_users = []
        skipped_users = []

        for req in enrollment_requests:  # noqa: PLR1702
            # Handle cancellation
            if req.choice == "cancel":
                existing_participation = SessionParticipation.objects.filter(
                    session=session, user=req.user
                ).first()

                if existing_participation:
                    was_confirmed = (
                        existing_participation.status
                        == SessionParticipationStatus.CONFIRMED
                    )
                    existing_participation.delete()
                    cancelled_users.append(req.name)

                    # If this was a confirmed enrollment, promote from waiting list
                    if was_confirmed:
                        oldest_waiting = (
                            SessionParticipation.objects.filter(
                                session=session,
                                status=SessionParticipationStatus.WAITING,
                            )
                            .order_by("creation_time")
                            .first()
                        )

                        if oldest_waiting:
                            # Check for time conflicts before promoting
                            if session.start_time and session.end_time:
                                conflicting_sessions = Session.objects.filter(
                                    session_participations__user=oldest_waiting.user,
                                    session_participations__status=SessionParticipationStatus.CONFIRMED,
                                    start_time__lt=session.end_time,
                                    end_time__gt=session.start_time,
                                ).exclude(id=session.id)

                                if not conflicting_sessions.exists():
                                    oldest_waiting.status = (
                                        SessionParticipationStatus.CONFIRMED
                                    )
                                    oldest_waiting.save()
                                    promoted_msg = _("promoted from waiting list")
                                    req.name = oldest_waiting.user.get_full_name()
                                    enrolled_users.append(
                                        f"{req.name} ({promoted_msg!s})"
                                    )
                            else:
                                oldest_waiting.status = (
                                    SessionParticipationStatus.CONFIRMED
                                )
                                oldest_waiting.save()
                                promoted_msg = _("promoted from waiting list")
                                req.name = oldest_waiting.user.get_full_name()
                                enrolled_users.append(f"{req.name} ({promoted_msg!s})")
                else:
                    skipped_users.append(f"{req.name} ({_('not enrolled')!s})")
                continue

            # Check if user is already enrolled
            existing_participation = SessionParticipation.objects.filter(
                session=session, user=req.user
            ).first()

            if existing_participation:
                skipped_users.append(f"{req.name} ({_('already enrolled')!s})")
                continue

            # Check for time conflicts for confirmed enrollment
            if req.choice == "enroll" and session.start_time and session.end_time:
                conflicting_sessions = Session.objects.filter(
                    session_participations__user=req.user,
                    session_participations__status=SessionParticipationStatus.CONFIRMED,
                    start_time__lt=session.end_time,
                    end_time__gt=session.start_time,
                ).exclude(id=session.id)

                if conflicting_sessions.exists():
                    skipped_users.append(f"{req.name} ({_('time conflict')!s})")
                    continue

            # Create enrollment
            status = (
                SessionParticipationStatus.CONFIRMED
                if req.choice == "enroll"
                else SessionParticipationStatus.WAITING
            )

            SessionParticipation.objects.create(
                session=session, user=req.user, status=status
            )

            if status == SessionParticipationStatus.CONFIRMED:
                enrolled_users.append(req.name)
            else:
                waitlisted_users.append(req.name)

        # Create success message
        message_parts = []
        if enrolled_users:
            message_parts.append(_("Enrolled: {}").format(", ".join(enrolled_users)))
        if waitlisted_users:
            message_parts.append(
                _("Added to waiting list: {}").format(", ".join(waitlisted_users))
            )
        if cancelled_users:
            message_parts.append(_("Cancelled: {}").format(", ".join(cancelled_users)))
        if skipped_users:
            message_parts.append(
                _("Skipped (already enrolled or conflicts): {}").format(
                    ", ".join(skipped_users)
                )
            )

        if message_parts:
            messages.success(request, " | ".join(message_parts))
        else:
            messages.warning(request, _("No enrollments were processed."))

        return redirect("web:event", slug=event.slug)


class ProposeSessionView(LoginRequiredMixin, View):
    def get(
        self, request: UserRequest, event_slug: str, time_slot_id: int | None = None
    ) -> HttpResponse:
        try:
            event = Event.objects.get(sphere=request.sphere, slug=event_slug)
        except Event.DoesNotExist:
            messages.error(self.request, _("Event not found."))
            return redirect("web:index")

        # Check if user has birth date set
        if not request.user.birth_date:
            messages.error(
                request,
                _(
                    "Please complete your profile with birth date "
                    "before submitting proposals."
                ),
            )
            return redirect("web:edit")

        if not event.is_proposal_active:
            messages.error(
                request,
                _("Proposal submission is not currently active for this event."),
            )
            return redirect("web:event", slug=event_slug)

        try:
            proposal_category = ProposalCategory.objects.get(event=event)
        except ProposalCategory.DoesNotExist:
            messages.error(
                request,
                _(
                    "No proposal category configured for this event. "
                    "Please contact the organizers."
                ),
            )
            return redirect("web:event", slug=event_slug)

        # Get tag categories associated with the proposal category
        tag_categories = proposal_category.tag_categories.all()

        # Get confirmed tags for select-type categories
        confirmed_tags = {}
        for category in tag_categories:
            if category.input_type == category.InputType.SELECT:
                confirmed_tags[str(category.id)] = list(
                    category.tags.filter(confirmed=True).values("id", "name")
                )

        time_slot = None
        if time_slot_id:
            try:
                time_slot = TimeSlot.objects.get(id=time_slot_id, event=event)
            except TimeSlot.DoesNotExist:
                messages.error(self.request, _("Time slot not found."))
                return redirect("web:event", slug=event_slug)

        context = {
            "event": event,
            "time_slot": time_slot,
            "tag_categories": tag_categories,
            "confirmed_tags": confirmed_tags,
            "min_participants_limit": proposal_category.min_participants_limit,
            "max_participants_limit": proposal_category.max_participants_limit,
        }

        return TemplateResponse(request, "chronology/propose_session.html", context)

    def post(  # noqa: PLR0912, PLR0911, C901
        self, request: UserRequest, event_slug: str, time_slot_id: int | None = None
    ) -> HttpResponse:
        try:
            event = Event.objects.get(sphere=request.sphere, slug=event_slug)
        except Event.DoesNotExist:
            messages.error(self.request, _("Event not found."))
            return redirect("web:index")

        # Check if user has birth date set
        if not request.user.birth_date:
            messages.error(
                request,
                _(
                    "Please complete your profile with birth date before "
                    "submitting proposals."
                ),
            )
            return redirect("web:edit")

        if not event.is_proposal_active:
            messages.error(
                request,
                _("Proposal submission is not currently active for this event."),
            )
            return redirect("web:event", slug=event_slug)

        # Get form data
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        requirements = request.POST.get("requirements", "").strip()
        needs = request.POST.get("needs", "").strip()
        participants_limit = int(request.POST.get("participants_limit", "10"))

        if not title:
            messages.error(self.request, _("Session title is required."))
            return redirect(
                "web:propose-session", event_slug=event_slug, time_slot_id=time_slot_id
            )

        try:
            proposal_category = ProposalCategory.objects.get(event=event)
        except ProposalCategory.DoesNotExist:
            messages.error(
                request,
                _(
                    "No proposal category configured for this event. "
                    "Please contact the organizers."
                ),
            )
            return redirect("web:event", slug=event_slug)

        # Validate participants limit against proposal category settings
        if (
            participants_limit < proposal_category.min_participants_limit
            or participants_limit > proposal_category.max_participants_limit
        ):
            messages.error(
                request,
                _("Participants limit must be between {} and {}.").format(
                    proposal_category.min_participants_limit,
                    proposal_category.max_participants_limit,
                ),
            )
            return redirect(
                "web:propose-session", event_slug=event_slug, time_slot_id=time_slot_id
            )

        # Create the proposal
        proposal = Proposal.objects.create(
            proposal_category=proposal_category,
            host=request.user,
            title=title,
            description=description,
            requirements=requirements,
            needs=needs,
            participants_limit=participants_limit,
        )

        # Process tags
        for category in proposal_category.tag_categories.all():
            if category.input_type == category.InputType.SELECT:
                # Handle multiple select input
                category_key = f"tags_{category.id}"
                selected_tag_ids = request.POST.getlist(category_key)
                for tag_id in selected_tag_ids:
                    try:
                        tag = Tag.objects.get(id=tag_id, category=category)
                        proposal.tags.add(tag)
                    except (Tag.DoesNotExist, ValueError):
                        pass
            elif category.input_type == category.InputType.TYPE:
                # Handle comma-separated text input
                category_key = f"tags_{category.id}"
                tag_text = request.POST.get(category_key, "").strip()
                if tag_text:
                    tag_names = [
                        name.strip() for name in tag_text.split(",") if name.strip()
                    ]
                    for tag_name in tag_names:
                        tag, _created = Tag.objects.get_or_create(
                            name=tag_name,
                            category=category,
                            defaults={"confirmed": False},
                        )
                        proposal.tags.add(tag)

        # Add time slot preference if specified
        if time_slot_id:
            try:
                time_slot = TimeSlot.objects.get(id=time_slot_id, event=event)
                proposal.time_slots.add(time_slot)
            except TimeSlot.DoesNotExist:
                pass

        messages.success(
            request, _("Session proposal '{}' submitted successfully!").format(title)
        )
        return redirect("web:event", slug=event_slug)


class AcceptProposalPageView(LoginRequiredMixin, View):

    @staff_member_required
    def get(self, request: UserRequest, proposal_id: int) -> HttpResponse:
        try:
            proposal = Proposal.objects.get(
                proposal_category__event__sphere=request.sphere, id=proposal_id
            )
        except Proposal.DoesNotExist:
            messages.error(self.request, _("Proposal not found."))
            return redirect("web:index")

        proposal = Proposal.objects.get(id=proposal_id)
        event = proposal.proposal_category.event

        # Check if proposal is already accepted
        if proposal.session:
            messages.warning(request, _("This proposal has already been accepted."))
            return redirect("web:event", slug=event.slug)

        # Get available spaces and time slots for the event
        spaces = Space.objects.filter(event=event)
        time_slots = TimeSlot.objects.filter(event=event)

        # Check if there are any spaces or time slots
        if not spaces.exists():
            messages.error(
                request,
                _("No spaces configured for this event. Please create spaces first."),
            )
            return redirect("web:event", slug=event.slug)

        if not time_slots.exists():
            messages.error(
                request,
                _(
                    "No time slots configured for this event. "
                    "Please create time slots first."
                ),
            )
            return redirect("web:event", slug=event.slug)

        context = {
            "proposal": proposal,
            "event": event,
            "spaces": spaces,
            "time_slots": time_slots,
        }

        return TemplateResponse(request, "chronology/accept_proposal.html", context)


class AcceptProposalView(LoginRequiredMixin, View):
    @staff_member_required
    def post(self, request: UserRequest, proposal_id: int) -> HttpResponse:
        try:
            proposal = Proposal.objects.get(
                proposal_category__event__sphere=request.sphere, id=proposal_id
            )
        except Proposal.DoesNotExist:
            messages.error(self.request, _("Proposal not found."))
            return redirect("web:index")

        event = proposal.proposal_category.event

        # Check if proposal is already accepted
        if proposal.session:
            messages.warning(request, _("This proposal has already been accepted."))
            return redirect("web:event", slug=event.slug)

        # Get form data
        space_id = request.POST.get("space_id")
        time_slot_id = request.POST.get("time_slot_id")

        if not space_id:
            messages.error(self.request, _("Please select a space."))
            return redirect("web:accept-proposal-page", proposal_id=proposal_id)

        if not time_slot_id:
            messages.error(self.request, _("Please select a time slot."))
            return redirect("web:accept-proposal-page", proposal_id=proposal_id)

        try:
            space = Space.objects.get(id=space_id, event=event)
            time_slot = TimeSlot.objects.get(id=time_slot_id, event=event)
        except (Space.DoesNotExist, TimeSlot.DoesNotExist):
            messages.error(self.request, _("Selected space or time slot is invalid."))
            return redirect("web:accept-proposal-page", proposal_id=proposal_id)

        # Create a session from the proposal
        session = Session.objects.create(
            sphere=event.sphere,
            host=proposal.host,
            title=proposal.title,
            description=proposal.description,
            requirements=proposal.requirements,
            participants_limit=proposal.participants_limit,
            start_time=time_slot.start_time,
            end_time=time_slot.end_time,
            publication_time=datetime.now(tz=UTC),
        )

        # Copy tags from proposal to session
        session.tags.set(proposal.tags.all())

        AgendaItem.objects.create(space=space, session=session, session_confirmed=True)

        # Link proposal to session
        proposal.session = session
        proposal.save()

        messages.success(
            request,
            _("Proposal '{}' has been accepted and added to the agenda.").format(
                proposal.title
            ),
        )
        return redirect("web:event", slug=event.slug)
