import json
from datetime import UTC, date, datetime, timedelta
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus, urlencode, urlparse

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic.base import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from ludamus.adapters.db.django.models import (
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

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User
else:
    User = get_user_model()


TODAY = datetime.now(tz=UTC).date()
SEPARATOR = "|"


class UserRequest(HttpRequest):
    user: User


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
    last = get_current_site(request).domain
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


class EventView(DetailView):
    template_name = "chronology/event.html"
    model = Event
    context_object_name = "event"

    def get_queryset(self) -> QuerySet[Event]:
        return (
            Event.objects.filter(sphere=get_current_site(self.request).sphere)
            .select_related("sphere")
            .prefetch_related("spaces__agenda_items__session")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
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

        # Add user participation info for each session
        if self.request.user.is_authenticated:
            user_participations = SessionParticipation.objects.filter(
                user=self.request.user, session__in=event_sessions
            ).select_related("session")

            participation_by_session = {}
            for participation in user_participations:
                participation_by_session[participation.session.id] = participation

            # Get confirmed enrollments for time conflict checking
            confirmed_sessions = [
                p.session
                for p in user_participations
                if p.status == SessionParticipationStatus.CONFIRMED
            ]

            # Get connected users enrollments for checking if any enrollments exist
            connected_users = self.request.user.connected.all()
            connected_participations = SessionParticipation.objects.filter(
                user__in=connected_users, session__in=event_sessions
            ).select_related("session", "user")

            connected_participations_by_session = {}
            for participation in connected_participations:
                if participation.session.id not in connected_participations_by_session:
                    connected_participations_by_session[participation.session.id] = []
                connected_participations_by_session[participation.session.id].append(
                    participation
                )

            for session in event_sessions:
                participation = participation_by_session.get(session.id)
                if participation:
                    session.user_enrolled = (
                        participation.status == SessionParticipationStatus.CONFIRMED
                    )
                    session.user_waiting = (
                        participation.status == SessionParticipationStatus.WAITING
                    )
                    session.has_time_conflict = False
                else:
                    session.user_enrolled = False
                    session.user_waiting = False
                    # Check for time conflicts with confirmed enrollments
                    session.has_time_conflict = False
                    if session.start_time and session.end_time:
                        for confirmed_session in confirmed_sessions:
                            if (
                                confirmed_session.start_time
                                and confirmed_session.end_time
                                and confirmed_session.start_time < session.end_time
                                and confirmed_session.end_time > session.start_time
                            ):
                                session.has_time_conflict = True
                                break

                # Check if user or any connected users are enrolled
                session.has_any_enrollments = (
                    session.user_enrolled
                    or session.user_waiting
                    or bool(connected_participations_by_session.get(session.id))
                )

        # Add separate counts for enrolled and waiting participants for all sessions
        for session in event_sessions:
            session.enrolled_count = session.session_participations.filter(
                status=SessionParticipationStatus.CONFIRMED
            ).count()
            session.waiting_count = session.session_participations.filter(
                status=SessionParticipationStatus.WAITING
            ).count()

        # Group sessions by time slots
        from collections import defaultdict

        time_slots = TimeSlot.objects.filter(event=self.object).order_by("start_time")
        sessions_by_slot = defaultdict(list)

        for session in event_sessions:
            # Find matching time slot for this session
            matching_slot = None
            for slot in time_slots:
                if (
                    session.start_time
                    and session.end_time
                    and slot.start_time <= session.start_time
                    and slot.end_time >= session.end_time
                ):
                    matching_slot = slot
                    break

            if matching_slot:
                sessions_by_slot[matching_slot].append(session)
            else:
                # Sessions without matching time slots go to a special "Other" category
                sessions_by_slot[None].append(session)

        # Convert to list of (time_slot, sessions) tuples for template
        time_slot_data = []
        for slot in time_slots:
            time_slot_data.append(
                {
                    "time_slot": slot,
                    "sessions": sessions_by_slot[slot],
                    "session_count": len(sessions_by_slot[slot]),
                }
            )

        context["time_slot_data"] = time_slot_data
        context["unscheduled_sessions"] = sessions_by_slot[None]
        context["sessions"] = event_sessions  # Keep for backward compatibility

        # Add proposals for superusers
        if self.request.user.is_superuser:
            from ludamus.adapters.db.django.models import Proposal

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


class EnrollSelectView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, session_id: int) -> HttpResponse:
        try:
            session = Session.objects.get(id=session_id)
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

            # Check user's enrollment status and time conflicts
            user_participation = SessionParticipation.objects.filter(
                session=session, user=request.user
            ).first()

            session.user_enrolled = (
                user_participation.status == SessionParticipationStatus.CONFIRMED
                if user_participation
                else False
            )
            session.user_waiting = (
                user_participation.status == SessionParticipationStatus.WAITING
                if user_participation
                else False
            )

            # Check for time conflicts
            session.has_time_conflict = False
            if session.start_time and session.end_time and not user_participation:
                conflicting_sessions = Session.objects.filter(
                    session_participations__user=request.user,
                    session_participations__status=SessionParticipationStatus.CONFIRMED,
                    start_time__lt=session.end_time,
                    end_time__gt=session.start_time,
                ).exclude(id=session.id)
                session.has_time_conflict = conflicting_sessions.exists()

            # Add participant counts
            session.enrolled_count = session.session_participations.filter(
                status=SessionParticipationStatus.CONFIRMED
            ).count()
            session.waiting_count = session.session_participations.filter(
                status=SessionParticipationStatus.WAITING
            ).count()

            # Get connected users with their statuses
            connected_users = request.user.connected.all()

            # Add enrollment status and time conflict info for each connected user
            for connected_user in connected_users:
                user_participation = SessionParticipation.objects.filter(
                    session=session, user=connected_user
                ).first()

                connected_user.is_enrolled_in_session = (
                    user_participation.status == SessionParticipationStatus.CONFIRMED
                    if user_participation
                    else False
                )
                connected_user.is_waiting_in_session = (
                    user_participation.status == SessionParticipationStatus.WAITING
                    if user_participation
                    else False
                )

                # Check for time conflicts
                connected_user.has_time_conflicts = False
                if session.start_time and session.end_time and not user_participation:
                    conflicting_sessions = Session.objects.filter(
                        session_participations__user=connected_user,
                        session_participations__status=SessionParticipationStatus.CONFIRMED,
                        start_time__lt=session.end_time,
                        end_time__gt=session.start_time,
                    ).exclude(id=session.id)
                    connected_user.has_time_conflicts = conflicting_sessions.exists()

            context = {
                "session": session,
                "event": event,
                "connected_users": connected_users,
            }

            return TemplateResponse(request, "chronology/enroll_select.html", context)

        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")

    def post(self, request: HttpRequest, session_id: int) -> HttpResponse:
        try:
            session = Session.objects.get(id=session_id)
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

            # Check for user_self selection
            self_choice = request.POST.get("user_self")
            if self_choice in {"enroll", "waitlist", "cancel"}:
                enrollment_requests.append(
                    {"user": request.user, "type": self_choice, "name": _("yourself")}
                )

            # Check for connected users selections
            connected_users = request.user.connected.all()
            for connected_user in connected_users:
                choice = request.POST.get(f"user_{connected_user.id}")
                if choice in {"enroll", "waitlist", "cancel"}:
                    enrollment_requests.append(
                        {
                            "user": connected_user,
                            "type": choice,
                            "name": connected_user.get_full_name(),
                        }
                    )

            if not enrollment_requests:
                messages.warning(
                    request, _("Please select at least one user to enroll.")
                )
                return redirect("web:enroll-select", session_id=session_id)

            # Validate capacity for confirmed enrollments
            confirmed_requests = [
                req for req in enrollment_requests if req["type"] == "enroll"
            ]
            current_confirmed = session.session_participations.filter(
                status=SessionParticipationStatus.CONFIRMED
            ).count()
            available_spots = session.participants_limit - current_confirmed

            if len(confirmed_requests) > available_spots:
                messages.error(
                    request,
                    _(
                        "Not enough spots available. {} spots requested, {} available. "
                        "Please use waiting list for some users."
                    ).format(len(confirmed_requests), available_spots),
                )
                return redirect("web:enroll-select", session_id=session_id)

            # Process enrollments
            enrolled_users = []
            waitlisted_users = []
            cancelled_users = []
            skipped_users = []

            for req in enrollment_requests:
                target_user = req["user"]
                enroll_type = req["type"]
                user_name = req["name"]

                # Handle cancellation
                if enroll_type == "cancel":
                    existing_participation = SessionParticipation.objects.filter(
                        session=session, user=target_user
                    ).first()

                    if existing_participation:
                        was_confirmed = (
                            existing_participation.status
                            == SessionParticipationStatus.CONFIRMED
                        )
                        existing_participation.delete()
                        cancelled_users.append(str(user_name))

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
                                        user_name = oldest_waiting.user.get_full_name()
                                        enrolled_users.append(
                                            f"{user_name} ({promoted_msg!s})"
                                        )
                                else:
                                    oldest_waiting.status = (
                                        SessionParticipationStatus.CONFIRMED
                                    )
                                    oldest_waiting.save()
                                    promoted_msg = _("promoted from waiting list")
                                    user_name = oldest_waiting.user.get_full_name()
                                    enrolled_users.append(
                                        f"{user_name} ({promoted_msg!s})"
                                    )
                    else:
                        skipped_users.append(f"{user_name} ({_('not enrolled')!s})")
                    continue

                # Check if user is already enrolled
                existing_participation = SessionParticipation.objects.filter(
                    session=session, user=target_user
                ).first()

                if existing_participation:
                    skipped_users.append(f"{user_name} ({_('already enrolled')!s})")
                    continue

                # Check for time conflicts for confirmed enrollment
                if enroll_type == "enroll" and session.start_time and session.end_time:
                    conflicting_sessions = Session.objects.filter(
                        session_participations__user=target_user,
                        session_participations__status=SessionParticipationStatus.CONFIRMED,
                        start_time__lt=session.end_time,
                        end_time__gt=session.start_time,
                    ).exclude(id=session.id)

                    if conflicting_sessions.exists():
                        skipped_users.append(f"{user_name} ({_('time conflict')!s})")
                        continue

                # Create enrollment
                status = (
                    SessionParticipationStatus.CONFIRMED
                    if enroll_type == "enroll"
                    else SessionParticipationStatus.WAITING
                )

                SessionParticipation.objects.create(
                    session=session, user=target_user, status=status
                )

                if status == SessionParticipationStatus.CONFIRMED:
                    enrolled_users.append(str(user_name))
                else:
                    waitlisted_users.append(str(user_name))

            # Create success message
            message_parts = []
            if enrolled_users:
                message_parts.append(
                    str(_("Enrolled: {}")).format(", ".join(enrolled_users))
                )
            if waitlisted_users:
                message_parts.append(
                    str(_("Added to waiting list: {}")).format(
                        ", ".join(waitlisted_users)
                    )
                )
            if cancelled_users:
                message_parts.append(
                    str(_("Cancelled: {}")).format(", ".join(cancelled_users))
                )
            if skipped_users:
                message_parts.append(
                    str(_("Skipped (already enrolled or conflicts): {}")).format(
                        ", ".join(skipped_users)
                    )
                )

            if message_parts:
                messages.success(request, " | ".join(message_parts))
            else:
                messages.warning(request, _("No enrollments were processed."))

            return redirect("web:event", slug=event.slug)

        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")


class EnrollSessionView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, session_id: int) -> HttpResponse:
        try:
            session = Session.objects.get(id=session_id)

            # Check if user is connected type or active
            if request.user.user_type not in {
                User.UserType.CONNECTED,
                User.UserType.ACTIVE,
            }:
                messages.error(
                    request, _("Only connected or active users can enroll in sessions.")
                )
                return redirect("web:event", slug=session.agenda_item.space.event.slug)

            # Check if user has birth date set
            if not request.user.birth_date:
                messages.error(
                    request,
                    _("Please complete your profile with birth date before enrolling."),
                )
                return redirect("web:edit")

            # Check if enrollment is active for the event
            event = session.agenda_item.space.event
            if not event.is_enrollment_active:
                messages.error(
                    request, _("Enrollment is not currently active for this event.")
                )
                return redirect("web:event", slug=event.slug)

            # Check if session is full
            if session.session_participations.count() >= session.participants_limit:
                messages.error(request, _("This session is already full."))
                return redirect("web:event", slug=event.slug)

            # Check if user is already enrolled
            if SessionParticipation.objects.filter(
                session=session, user=request.user
            ).exists():
                messages.warning(
                    request, _("You are already enrolled in this session.")
                )
                return redirect("web:event", slug=event.slug)

            # Check for time conflicts with user's other enrolled sessions
            if session.start_time and session.end_time:
                conflicting_sessions = Session.objects.filter(
                    session_participations__user=request.user,
                    start_time__lt=session.end_time,
                    end_time__gt=session.start_time,
                ).exclude(id=session.id)

                if conflicting_sessions.exists():
                    conflicting_session = conflicting_sessions.first()
                    messages.error(
                        request,
                        _(
                            "You are already enrolled in '{}' which overlaps with this session's time."
                        ).format(conflicting_session.title),
                    )
                    return redirect("web:event", slug=event.slug)

            # Create enrollment
            SessionParticipation.objects.create(
                session=session,
                user=request.user,
                status=SessionParticipationStatus.CONFIRMED,
            )

            messages.success(
                request,
                _("Successfully enrolled in session '{}'").format(session.title),
            )
            return redirect("web:event", slug=event.slug)

        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")


class CancelEnrollmentView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, session_id: int) -> HttpResponse:
        try:
            session = Session.objects.get(id=session_id)
            event = session.agenda_item.space.event

            # Find and delete the participation
            participation = SessionParticipation.objects.filter(
                session=session, user=request.user
            ).first()

            if not participation:
                messages.warning(request, _("You are not enrolled in this session."))
                return redirect("web:event", slug=event.slug)

            # Check if this was a confirmed enrollment (to potentially promote from waiting list)
            was_confirmed = participation.status == SessionParticipationStatus.CONFIRMED

            participation.delete()

            # If this was a confirmed enrollment, promote the oldest waiting list user
            if was_confirmed:
                # Find the oldest waiting list participant
                oldest_waiting = (
                    SessionParticipation.objects.filter(
                        session=session, status=SessionParticipationStatus.WAITING
                    )
                    .order_by("creation_time")
                    .first()
                )

                promoted_user = None
                if oldest_waiting:
                    # Check for time conflicts with the waiting user's other confirmed enrollments
                    if session.start_time and session.end_time:
                        conflicting_sessions = Session.objects.filter(
                            session_participations__user=oldest_waiting.user,
                            session_participations__status=SessionParticipationStatus.CONFIRMED,
                            start_time__lt=session.end_time,
                            end_time__gt=session.start_time,
                        ).exclude(id=session.id)

                        if not conflicting_sessions.exists():
                            # No time conflict, promote the user
                            oldest_waiting.status = SessionParticipationStatus.CONFIRMED
                            oldest_waiting.save()
                            promoted_user = oldest_waiting.user
                        # If there's a time conflict, skip this user and try the next one
                        else:
                            # Find the next available waiting list user without conflicts
                            remaining_waiting = SessionParticipation.objects.filter(
                                session=session,
                                status=SessionParticipationStatus.WAITING,
                            ).order_by("creation_time")

                            for waiting_participation in remaining_waiting:
                                user_conflicts = Session.objects.filter(
                                    session_participations__user=waiting_participation.user,
                                    session_participations__status=SessionParticipationStatus.CONFIRMED,
                                    start_time__lt=session.end_time,
                                    end_time__gt=session.start_time,
                                ).exclude(id=session.id)

                                if not user_conflicts.exists():
                                    # No conflict found, promote this user
                                    waiting_participation.status = (
                                        SessionParticipationStatus.CONFIRMED
                                    )
                                    waiting_participation.save()
                                    promoted_user = waiting_participation.user
                                    break
                    else:
                        # No time constraints, promote the oldest waiting user
                        oldest_waiting.status = SessionParticipationStatus.CONFIRMED
                        oldest_waiting.save()
                        promoted_user = oldest_waiting.user

                if promoted_user:
                    messages.success(
                        request,
                        _(
                            "Successfully cancelled enrollment in session '{}'. {} has been promoted from the waiting list."
                        ).format(session.title, promoted_user.get_full_name()),
                    )
                else:
                    messages.success(
                        request,
                        _("Successfully cancelled enrollment in session '{}'").format(
                            session.title
                        ),
                    )
            else:
                messages.success(
                    request,
                    _("Successfully cancelled enrollment in session '{}'").format(
                        session.title
                    ),
                )
            return redirect("web:event", slug=event.slug)

        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")


class EnrollWaitingListView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, session_id: int) -> HttpResponse:
        try:
            session = Session.objects.get(id=session_id)

            # Check if user is connected type or active
            if request.user.user_type not in {
                User.UserType.CONNECTED,
                User.UserType.ACTIVE,
            }:
                messages.error(
                    request, _("Only connected or active users can join waiting lists.")
                )
                return redirect("web:event", slug=session.agenda_item.space.event.slug)

            # Check if user has birth date set
            if not request.user.birth_date:
                messages.error(
                    request,
                    _("Please complete your profile with birth date before enrolling."),
                )
                return redirect("web:edit")

            # Check if enrollment is active for the event
            event = session.agenda_item.space.event
            if not event.is_enrollment_active:
                messages.error(
                    request, _("Enrollment is not currently active for this event.")
                )
                return redirect("web:event", slug=event.slug)

            # Check if user is already enrolled (confirmed or waiting)
            existing_participation = SessionParticipation.objects.filter(
                session=session, user=request.user
            ).first()

            if existing_participation:
                if (
                    existing_participation.status
                    == SessionParticipationStatus.CONFIRMED
                ):
                    messages.warning(
                        request, _("You are already enrolled in this session.")
                    )
                else:
                    messages.warning(
                        request,
                        _("You are already on the waiting list for this session."),
                    )
                return redirect("web:event", slug=event.slug)

            # Create waiting list enrollment
            SessionParticipation.objects.create(
                session=session,
                user=request.user,
                status=SessionParticipationStatus.WAITING,
            )

            messages.success(
                request,
                _("Successfully joined waiting list for session '{}'").format(
                    session.title
                ),
            )
            return redirect("web:event", slug=event.slug)

        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")


class CancelWaitingListView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, session_id: int) -> HttpResponse:
        try:
            session = Session.objects.get(id=session_id)
            event = session.agenda_item.space.event

            # Find and delete the waiting list participation
            participation = SessionParticipation.objects.filter(
                session=session,
                user=request.user,
                status=SessionParticipationStatus.WAITING,
            ).first()

            if not participation:
                messages.warning(
                    request, _("You are not on the waiting list for this session.")
                )
                return redirect("web:event", slug=event.slug)

            participation.delete()
            messages.success(
                request,
                _("Successfully left waiting list for session '{}'").format(
                    session.title
                ),
            )
            return redirect("web:event", slug=event.slug)

        except Session.DoesNotExist:
            messages.error(request, _("Session not found."))
            return redirect("web:index")


class ProposeSessionView(LoginRequiredMixin, View):
    def get(
        self, request: HttpRequest, event_slug: str, time_slot_id: int | None = None
    ) -> HttpResponse:
        # Check if user has birth date set
        if not request.user.birth_date:
            messages.error(
                request,
                _(
                    "Please complete your profile with birth date before submitting proposals."
                ),
            )
            return redirect("web:edit")

        try:
            event = Event.objects.get(slug=event_slug)

            if not event.is_proposal_active:
                messages.error(
                    request,
                    _("Proposal submission is not currently active for this event."),
                )
                return redirect("web:event", slug=event_slug)

            # Get the proposal category for this event (should be only one, created by admin)
            try:
                proposal_category = ProposalCategory.objects.get(event=event)
            except ProposalCategory.DoesNotExist:
                messages.error(
                    request,
                    _(
                        "No proposal category configured for this event. Please contact the organizers."
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

            context = {
                "event": event,
                "time_slot": None,
                "tag_categories": tag_categories,
                "confirmed_tags": confirmed_tags,
                "min_participants_limit": proposal_category.min_participants_limit,
                "max_participants_limit": proposal_category.max_participants_limit,
            }

            if time_slot_id:
                try:
                    time_slot = TimeSlot.objects.get(id=time_slot_id, event=event)
                    context["time_slot"] = time_slot
                except TimeSlot.DoesNotExist:
                    messages.error(request, _("Time slot not found."))
                    return redirect("web:event", slug=event_slug)

            return TemplateResponse(request, "chronology/propose_session.html", context)

        except Event.DoesNotExist:
            messages.error(request, _("Event not found."))
            return redirect("web:index")

    def post(
        self, request: HttpRequest, event_slug: str, time_slot_id: int | None = None
    ) -> HttpResponse:
        # Check if user has birth date set
        if not request.user.birth_date:
            messages.error(
                request,
                _(
                    "Please complete your profile with birth date before submitting proposals."
                ),
            )
            return redirect("web:edit")

        try:
            event = Event.objects.get(slug=event_slug)

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
            participants_limit = request.POST.get("participants_limit", "10")

            if not title:
                messages.error(request, _("Session title is required."))
                return redirect(
                    "web:propose-session",
                    event_slug=event_slug,
                    time_slot_id=time_slot_id,
                )

            # Get the event's proposal category (should exist, created by admin)
            from ludamus.adapters.db.django.models import Proposal

            try:
                proposal_category = ProposalCategory.objects.get(event=event)
            except ProposalCategory.DoesNotExist:
                messages.error(
                    request,
                    _(
                        "No proposal category configured for this event. Please contact the organizers."
                    ),
                )
                return redirect("web:event", slug=event_slug)

            # Validate participants limit against proposal category settings
            try:
                participants_limit = int(participants_limit)
                if (
                    participants_limit < proposal_category.min_participants_limit
                    or participants_limit > proposal_category.max_participants_limit
                ):
                    raise ValueError
            except ValueError:
                messages.error(
                    request,
                    _("Participants limit must be between {} and {}.").format(
                        proposal_category.min_participants_limit,
                        proposal_category.max_participants_limit,
                    ),
                )
                return redirect(
                    "web:propose-session",
                    event_slug=event_slug,
                    time_slot_id=time_slot_id,
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
                request,
                _("Session proposal '{}' submitted successfully!").format(title),
            )
            return redirect("web:event", slug=event_slug)

        except Event.DoesNotExist:
            messages.error(request, _("Event not found."))
            return redirect("web:index")


class AcceptProposalPageView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, proposal_id: int) -> HttpResponse:
        # Only superusers can accept proposals
        if not request.user.is_superuser:
            messages.error(request, _("You don't have permission to accept proposals."))
            return redirect("web:index")

        try:
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
                    _(
                        "No spaces configured for this event. Please create spaces first."
                    ),
                )
                return redirect("web:event", slug=event.slug)

            if not time_slots.exists():
                messages.error(
                    request,
                    _(
                        "No time slots configured for this event. Please create time slots first."
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

        except Proposal.DoesNotExist:
            messages.error(request, _("Proposal not found."))
            return redirect("web:index")


class AcceptProposalView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, proposal_id: int) -> HttpResponse:
        # Only superusers can accept proposals
        if not request.user.is_superuser:
            messages.error(request, _("You don't have permission to accept proposals."))
            return redirect("web:index")

        try:
            proposal = Proposal.objects.get(id=proposal_id)
            event = proposal.proposal_category.event

            # Check if proposal is already accepted
            if proposal.session:
                messages.warning(request, _("This proposal has already been accepted."))
                return redirect("web:event", slug=event.slug)

            # Get form data
            space_id = request.POST.get("space_id")
            time_slot_id = request.POST.get("time_slot_id")

            if not space_id:
                messages.error(request, _("Please select a space."))
                return redirect("web:accept-proposal-page", proposal_id=proposal_id)

            if not time_slot_id:
                messages.error(request, _("Please select a time slot."))
                return redirect("web:accept-proposal-page", proposal_id=proposal_id)

            try:
                space = Space.objects.get(id=space_id, event=event)
                time_slot = TimeSlot.objects.get(id=time_slot_id, event=event)
            except (Space.DoesNotExist, TimeSlot.DoesNotExist):
                messages.error(request, _("Selected space or time slot is invalid."))
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

            # Create agenda item to link session to event
            from ludamus.adapters.db.django.models import AgendaItem

            AgendaItem.objects.create(
                space=space, session=session, session_confirmed=True
            )

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

        except Proposal.DoesNotExist:
            messages.error(request, _("Proposal not found."))
            return redirect("web:index")
