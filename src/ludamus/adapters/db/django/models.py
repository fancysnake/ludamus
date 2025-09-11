from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING, ClassVar, Never

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Collection


MAX_SLUG_RETRIES = 10
RANDOM_SLUG_BYTES = 7  # 10 characters
DEFAULT_NAME = "Andrzej"
MAX_CONNECTED_USERS = 6  # Maximum number of connected users per manager


class User(AbstractBaseUser, PermissionsMixin):
    EMAIL_FIELD = "email"
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: ClassVar = ["email"]

    class UserType(models.TextChoices):  # pylint: disable=too-many-ancestors
        ACTIVE = "active", _("Active")
        CONNECTED = "connected", _("Connected")
        ANONYMOUS = "anonymous", _("Anonymous")

    birth_date = models.DateField(blank=True, null=True)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    email = models.EmailField(_("email address"), blank=True)
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    manager = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="connected",
    )
    name = models.CharField(_("User name"), max_length=255, blank=True)
    slug = models.SlugField(unique=True, db_index=True)
    user_type = models.CharField(
        max_length=255, choices=UserType, default=UserType.ACTIVE
    )
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        error_messages={"unique": _("A user with that username already exists.")},
    )

    objects = UserManager()

    def clean(self) -> None:
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def get_full_name(self) -> str:
        return self.name or DEFAULT_NAME

    def get_short_name(self) -> str:
        return self.name.split(" ")[0]

    class Meta:
        db_table = "user"
        verbose_name = _("user")
        verbose_name_plural = _("users")

        constraints = (
            models.UniqueConstraint(
                Lower("email").desc(),
                name="constraint_unique_email_lower_no_null",
                condition=~Q(email=""),
            ),
        )

    @property
    def age(self) -> int:
        if self.birth_date:
            return math.floor(
                (datetime.now(tz=UTC).date() - self.birth_date).days / 365.25
            )

        return 0

    @property
    def is_incomplete(self) -> bool:
        return not self.name and not self.birth_date and not self.email

    @property
    def confirmed_participations_count(self) -> int:
        """Get count of confirmed session participations."""
        if not self.email:
            return 0

        return SessionParticipation.objects.filter(
            user=self, status=SessionParticipationStatus.CONFIRMED
        ).count()

    @property
    def enrollment_access_count(self) -> int:
        """Get count of UserEnrollmentConfig entries (enrollment access permissions)."""
        if not self.email:
            return 0

        return UserEnrollmentConfig.objects.filter(
            user_email=self.email,
            allowed_slots__gt=0,  # Only count configs with actual slots
        ).count()


class Sphere(models.Model):
    """Big group for whole provinces, topics, organizations or big events."""

    name = models.CharField(max_length=255)
    site = models.OneToOneField(Site, on_delete=models.PROTECT, related_name="sphere")
    managers = models.ManyToManyField(User)

    class Meta:
        db_table = "sphere"

    def __str__(self) -> str:
        return self.name


class Event(models.Model):
    # Owner
    sphere = models.ForeignKey(Sphere, on_delete=models.CASCADE, related_name="events")
    # ID
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(default="", blank=True)
    # Time - start and end
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    # Publication time
    publication_time = models.DateTimeField(blank=True, null=True)
    # Proposal times
    proposal_start_time = models.DateTimeField(blank=True, null=True)
    proposal_end_time = models.DateTimeField(blank=True, null=True)
    # Filterable tag categories for session list
    filterable_tag_categories: models.ManyToManyField[TagCategory, Never] = (
        models.ManyToManyField(
            "TagCategory",
            blank=True,
            help_text="Tag categories that will appear as filters in the session list",
        )
    )

    class Meta:
        db_table = "event"
        constraints = (
            models.UniqueConstraint(
                fields=("sphere", "slug"), name="event_has_unique_slug_and_sphere"
            ),
            models.CheckConstraint(
                condition=Q(
                    publication_time__isnull=True,
                    start_time__isnull=True,
                    end_time__isnull=True,
                )
                | Q(
                    publication_time__lte=F("start_time"), start_time__lt=F("end_time")
                ),
                name="event_date_times",
            ),
        )

    def __str__(self) -> str:
        return self.name

    @property
    def is_proposal_active(self) -> bool:
        return (
            self.proposal_start_time is not None
            and self.proposal_end_time is not None
            and (
                self.proposal_start_time < datetime.now(tz=UTC) < self.proposal_end_time
            )
        )

    @property
    def is_live(self) -> bool:
        return self.start_time < datetime.now(tz=UTC) < self.end_time

    @property
    def is_ended(self) -> bool:
        return self.end_time < datetime.now(tz=UTC)

    @property
    def enrollment_config(self) -> EnrollmentConfig | None:
        return self.enrollment_configs.first()

    def get_active_enrollment_configs(self) -> list[EnrollmentConfig]:
        return [config for config in self.enrollment_configs.all() if config.is_active]

    def get_most_liberal_config(self, session: Session) -> EnrollmentConfig | None:
        eligible_configs = [
            config
            for config in self.get_active_enrollment_configs()
            if config.is_session_eligible(session)
        ]

        if not eligible_configs:
            return None

        return max(eligible_configs, key=lambda c: c.percentage_slots)

    def get_user_enrollment_config(
        self, user_email: str
    ) -> UserEnrollmentConfig | None:
        from ludamus.adapters.external.membership_api import (  # noqa: PLC0415
            get_or_create_user_enrollment_config,
        )

        total_slots = 0
        primary_config = None
        has_individual_config = False
        has_domain_config = False
        domain_config_source = None

        for config in self.get_active_enrollment_configs():
            config_found = False

            # Check for explicit user config
            user_config = config.user_configs.filter(user_email=user_email).first()
            if user_config:
                total_slots += user_config.allowed_slots
                if not primary_config:
                    primary_config = user_config
                has_individual_config = True
                config_found = True

            # Try to fetch from API if not found locally
            if not config_found:
                api_user_config = get_or_create_user_enrollment_config(
                    config, user_email
                )
                if api_user_config:
                    total_slots += api_user_config.allowed_slots
                    if not primary_config:
                        primary_config = api_user_config
                    has_individual_config = True
                    config_found = True

            # Always check for domain-based access regardless of individual config
            domain_config = self.get_domain_config_for_email(user_email, config)
            if domain_config:
                total_slots += domain_config.allowed_slots_per_user
                has_domain_config = True
                domain_config_source = domain_config
                if not primary_config:
                    # Create virtual config as primary
                    primary_config = domain_config.create_virtual_user_config(
                        user_email
                    )

        if not primary_config:
            return None

        # If we have multiple sources, create a combined virtual config
        if (
            has_individual_config and has_domain_config
        ) or total_slots != primary_config.allowed_slots:
            combined_config = UserEnrollmentConfig(
                enrollment_config=primary_config.enrollment_config,
                user_email=user_email,
                allowed_slots=total_slots,
                fetched_from_api=(
                    primary_config.fetched_from_api
                    if hasattr(primary_config, "fetched_from_api")
                    else False
                ),
            )
            # Mark as combined access
            combined_config._is_combined_access = True  # noqa: SLF001
            combined_config._has_individual_config = (  # noqa: SLF001
                has_individual_config
            )
            combined_config._has_domain_config = has_domain_config  # noqa: SLF001
            combined_config._domain_config_source = domain_config_source  # noqa: SLF001
            return combined_config

        return primary_config

    @staticmethod
    def get_domain_config_for_email(
        user_email: str, enrollment_config: EnrollmentConfig
    ) -> DomainEnrollmentConfig | None:
        if not user_email or "@" not in user_email:
            return None

        email_domain = user_email.split("@")[1].lower()

        return enrollment_config.domain_configs.filter(domain=email_domain).first()

    def has_domain_access(self, user_email: str) -> bool:
        return any(
            self.get_domain_config_for_email(user_email, config)
            for config in self.get_active_enrollment_configs()
        )


class EnrollmentConfig(models.Model):
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="enrollment_configs"
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    percentage_slots = models.PositiveIntegerField(
        default=100,
        help_text="Percentage of total session slots available for enrollment (1-100)",
    )
    limit_to_end_time = models.BooleanField(
        default=False,
        help_text=(
            "Only allow enrollment for sessions starting before this config's end time"
        ),
    )
    banner_text = models.TextField(
        blank=True, help_text="Banner text to display for active enrollments"
    )
    max_waitlist_sessions = models.PositiveIntegerField(
        default=10,
        help_text=(
            "Maximum number of sessions a user can join waitlist for "
            "(0 = waitlist disabled)"
        ),
    )
    restrict_to_configured_users = models.BooleanField(
        default=False,
        help_text=(
            "Only allow users with explicit UserEnrollmentConfig entries to enroll"
        ),
    )
    allow_anonymous_enrollment = models.BooleanField(
        default=False,
        help_text="Allow anonymous users to enroll without creating accounts",
    )

    class Meta:
        db_table = "enrollment_config"
        constraints = (
            models.CheckConstraint(
                condition=Q(start_time__lt=F("end_time")),
                name="enrollment_config_date_times",
            ),
            models.CheckConstraint(
                condition=Q(percentage_slots__gte=1, percentage_slots__lte=100),
                name="enrollment_config_percentage_range",
            ),
        )

    def __str__(self) -> str:
        return f"Enrollment config for {self.event.name}"

    @property
    def is_active(self) -> bool:
        return self.start_time < datetime.now(tz=UTC) < self.end_time

    def get_available_slots(self, session: Session) -> int:
        """Calculate available enrollment slots for a session based on percentage.

        Returns:
            Number of available slots for enrollment.
        """
        effective_limit = math.ceil(
            session.participants_limit * self.percentage_slots / 100
        )
        current_enrolled = session.enrolled_count
        return max(0, effective_limit - current_enrolled)

    def is_session_eligible(self, session: Session) -> bool:
        """Check if session is eligible for enrollment under this config.

        Returns:
            True if session can be enrolled in under this config.
        """
        if not self.is_active:
            return False

        if self.limit_to_end_time:
            return session.agenda_item.start_time < self.end_time

        return True


class UserEnrollmentConfig(models.Model):
    enrollment_config = models.ForeignKey(
        EnrollmentConfig, on_delete=models.CASCADE, related_name="user_configs"
    )
    user_email = models.EmailField(
        help_text="Email address of the user this configuration applies to"
    )
    allowed_slots = models.PositiveIntegerField(
        help_text=(
            "Maximum number of users (including connected users) that can "
            "be enrolled by this account"
        )
    )
    fetched_from_api = models.BooleanField(
        default=False, help_text="Whether this config was fetched from external API"
    )
    last_check = models.DateTimeField(
        null=True, blank=True, help_text="Last time the membership was checked via API"
    )

    _domain_config_source: DomainEnrollmentConfig | None
    _has_domain_config: bool | None
    _has_individual_config: bool | None
    _is_domain_based: bool | None
    _source_domain_config: DomainEnrollmentConfig | None
    _is_combined_access: bool | None

    class Meta:
        db_table = "user_enrollment_config"
        constraints = (
            models.UniqueConstraint(
                fields=["enrollment_config", "user_email"],
                name="unique_user_enrollment_config",
            ),
        )

    def __str__(self) -> str:
        return f"{self.user_email}: {self.allowed_slots} people enrollment limit"

    def get_used_slots(self) -> int:
        try:
            user = User.objects.get(email=self.user_email)
        except User.DoesNotExist:
            return 0

        # Get all users (main user + connected users)
        all_users = [user, *user.connected.all()]

        # Count unique users who have at least one confirmed enrollment
        users_with_enrollments = (
            SessionParticipation.objects.filter(
                status=SessionParticipationStatus.CONFIRMED,
                user__in=all_users,
                session__agenda_item__space__event=self.enrollment_config.event,
            )
            .values_list("user", flat=True)
            .distinct()
        )

        return len(users_with_enrollments)

    def get_available_slots(self) -> int:
        return max(0, self.allowed_slots - self.get_used_slots())

    def has_available_slots(self) -> bool:
        return self.allowed_slots > 0

    def can_enroll_users(self, users_to_enroll: list[User]) -> bool:
        try:
            user = User.objects.get(email=self.user_email)
        except User.DoesNotExist:
            return False

        # Get all users (main user + connected users)
        all_users = [user, *user.connected.all()]

        # Get currently enrolled users
        currently_enrolled = set(
            SessionParticipation.objects.filter(
                status=SessionParticipationStatus.CONFIRMED,
                user__in=all_users,
                session__agenda_item__space__event=self.enrollment_config.event,
            )
            .values_list("user_id", flat=True)
            .distinct()
        )

        # Add new users to enroll
        users_to_enroll_ids = {u.id for u in users_to_enroll if u in all_users}
        total_enrolled = currently_enrolled | users_to_enroll_ids

        return len(total_enrolled) <= self.allowed_slots

    def is_domain_based(self) -> bool:
        return bool(hasattr(self, "_is_domain_based") and self._is_domain_based)

    def is_combined_access(self) -> bool:
        return bool(hasattr(self, "_is_combined_access") and self._is_combined_access)

    def has_domain_access(self) -> bool:
        return self.is_domain_based() or bool(
            self.is_combined_access()
            and hasattr(self, "_has_domain_config")
            and self._has_domain_config
        )

    def has_individual_access(self) -> bool:
        return (not self.is_domain_based() and not self.is_combined_access()) or bool(
            self.is_combined_access()
            and hasattr(self, "_has_individual_config")
            and self._has_individual_config
        )

    def get_source_domain(self) -> str | None:
        if (
            self.is_domain_based()
            and hasattr(self, "_source_domain_config")
            and self._source_domain_config is not None
        ):
            return self._source_domain_config.domain
        if (
            self.is_combined_access()
            and hasattr(self, "_domain_config_source")
            and self._domain_config_source
        ):
            return self._domain_config_source.domain
        return None


class DomainEnrollmentConfig(models.Model):
    enrollment_config = models.ForeignKey(
        EnrollmentConfig, on_delete=models.CASCADE, related_name="domain_configs"
    )
    domain = models.CharField(
        max_length=255, help_text="Domain name (e.g. 'company.com', 'university.edu')"
    )
    allowed_slots_per_user = models.PositiveIntegerField(
        help_text=(
            "Default number of users (including connected users) that can be enrolled "
            "by accounts from this domain"
        )
    )

    class Meta:
        db_table = "domain_enrollment_config"
        constraints = (
            models.UniqueConstraint(
                fields=["enrollment_config", "domain"],
                name="unique_domain_enrollment_config",
            ),
        )

    def __str__(self) -> str:
        return (
            f"@{self.domain}: {self.allowed_slots_per_user} people enrollment "
            "limit per account"
        )

    def clean(self) -> None:
        super().clean()
        # Normalize domain to lowercase
        if self.domain:
            self.domain = self.domain.lower().strip()
            # Remove @ prefix if present
            self.domain = self.domain.removeprefix("@")
            # Basic domain validation
            if not self.domain or "." not in self.domain:
                raise ValidationError(
                    "Please enter a valid domain (e.g. 'company.com')"
                )

    def matches_email(self, email: str) -> bool:
        if not email or "@" not in email:
            return False
        email_domain = email.split("@")[1].lower()
        return email_domain == self.domain

    def create_virtual_user_config(self, user_email: str) -> UserEnrollmentConfig:
        # This creates a non-persistent UserEnrollmentConfig object
        # that behaves like a regular config but represents domain access
        virtual_config = UserEnrollmentConfig(
            enrollment_config=self.enrollment_config,
            user_email=user_email,
            allowed_slots=self.allowed_slots_per_user,
            fetched_from_api=False,
        )
        # Mark it as domain-based so we can identify it later
        virtual_config._is_domain_based = True  # noqa: SLF001
        virtual_config._source_domain_config = self  # noqa: SLF001
        return virtual_config


class Space(models.Model):
    # Owner
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="spaces")
    # ID
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    # Time
    creation_time = models.DateTimeField(auto_now_add=True)
    modification_time = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "space"
        constraints = (
            models.UniqueConstraint(
                fields=("slug", "event"), name="space_has_unique_slug_and_event"
            ),
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


class TimeSlot(models.Model):
    # Owner
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="time_slots"
    )
    # Time
    end_time = models.DateTimeField()
    start_time = models.DateTimeField()

    class Meta:
        db_table = "time_slot"
        constraints = (
            models.UniqueConstraint(
                fields=("event", "start_time", "end_time"),
                name="timeslot_has_unique_times_for_event",
            ),
            models.CheckConstraint(
                condition=Q(start_time__lt=F("end_time")), name="timeslot_date_times"
            ),
        )

    def __str__(self) -> str:
        ts_format = "%Y-%m-%d %H:%M"
        start = localtime(self.start_time).strftime(ts_format)
        if self.start_time.date() == self.end_time.date():
            ts_format = "%H:%M"
        end = localtime(self.end_time).strftime(ts_format)
        return f"{start} - {end} ({self.id})"

    def validate_unique(self, exclude: Collection[str] | None = None) -> None:
        super().validate_unique(exclude)
        event_slots = TimeSlot.objects.filter(event=self.event)
        conflicted = event_slots.filter(
            Q(start_time__gt=self.start_time, start_time__lt=self.end_time)
            | Q(end_time__gt=self.start_time, end_time__lt=self.end_time)
            | Q(start_time__lte=self.start_time, end_time__gte=self.end_time)
        ).last()
        if conflicted and conflicted != self:
            raise ValidationError(_("Time slots can't overlap!"))


class TagCategory(models.Model):
    class InputType(models.TextChoices):  # pylint: disable=too-many-ancestors
        SELECT = "select", _("Select from list")
        TYPE = "type", _("Type comma-separated")

    name = models.CharField(max_length=255)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Bootstrap icon name (e.g., 'tag', 'star', 'heart')",
    )
    input_type = models.CharField(
        max_length=10, choices=InputType.choices, default=InputType.SELECT
    )

    class Meta:
        db_table = "tag_category"

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        TagCategory, on_delete=models.CASCADE, related_name="tags"
    )
    confirmed = models.BooleanField(default=False)

    class Meta:
        db_table = "tag"
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["name", "category"], name="unique_tag_name_per_category"
            )
        ]

    def __str__(self) -> str:
        return self.name


class SessionManager(models.Manager["Session"]):
    def has_conflicts(self, session: Session, user: User) -> bool:
        return (
            self.get_queryset()
            .filter(
                agenda_item__space__event=session.agenda_item.space.event,
                session_participations__user=user,
                session_participations__status=SessionParticipationStatus.CONFIRMED,
            )
            .filter(
                Q(
                    agenda_item__start_time__gte=session.agenda_item.start_time,
                    agenda_item__start_time__lt=session.agenda_item.end_time,
                )
                | Q(
                    agenda_item__end_time__gt=session.agenda_item.start_time,
                    agenda_item__end_time__lte=session.agenda_item.end_time,
                )
            )
            .exclude(id=session.id)
            .exists()
        )


class Session(models.Model):
    """Session model."""

    # Owner
    sphere = models.ForeignKey(
        "Sphere", on_delete=models.CASCADE, related_name="sessions"
    )
    guild = models.ForeignKey(
        "Guild",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    presenter_name = models.CharField(max_length=255)
    # ID
    title = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(default="", blank=True)
    requirements = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    # Time
    creation_time = models.DateTimeField(auto_now_add=True)
    modification_time = models.DateTimeField(auto_now=True)
    # Participants
    participants_limit = models.PositiveIntegerField()
    min_age = models.PositiveIntegerField(
        default=0, help_text="Minimum age requirement (0 = no restriction)"
    )
    participants: models.ManyToManyField[User, Never] = models.ManyToManyField(
        User, through="SessionParticipation"
    )

    objects = SessionManager()

    enrolled_count_cached: int
    waiting_count_cached: int

    class Meta:
        db_table = "session"
        constraints = (
            models.UniqueConstraint(
                fields=["slug", "sphere"], name="session_unique_slug_in_sphere"
            ),
            models.CheckConstraint(
                condition=Q(min_age__gte=0, min_age__lte=18),
                name="session_min_age_range",
            ),
        )

    def __str__(self) -> str:
        return self.title

    @property
    def enrolled_count(self) -> int:
        # Use cached count if available from annotation, otherwise query
        if hasattr(self, "enrolled_count_cached"):
            return self.enrolled_count_cached
        return self.session_participations.filter(
            status=SessionParticipationStatus.CONFIRMED
        ).count()

    @property
    def waiting_count(self) -> int:
        # Use cached count if available from annotation, otherwise query
        if hasattr(self, "waiting_count_cached"):
            return self.waiting_count_cached
        return self.session_participations.filter(
            status=SessionParticipationStatus.WAITING
        ).count()

    @property
    def effective_participants_limit(self) -> int:
        """Get effective participants limit considering enrollment config percentage."""
        if enrollment_config := self.agenda_item.space.event.get_most_liberal_config(
            self
        ):
            return math.ceil(
                self.participants_limit * enrollment_config.percentage_slots / 100
            )
        return self.participants_limit

    @property
    def available_spots(self) -> int:
        """Get number of available enrollment spots."""
        return max(0, self.effective_participants_limit - self.enrolled_count)

    @property
    def is_full(self) -> bool:
        """Check if session is at capacity for enrollment."""
        return self.enrolled_count >= self.effective_participants_limit

    @property
    def is_enrollment_limited(self) -> bool:
        """Check if enrollment is limited by enrollment config percentage."""
        if enrollment_config := self.agenda_item.space.event.get_most_liberal_config(
            self
        ):
            return enrollment_config.percentage_slots < 100  # noqa: PLR2004
        return False

    @property
    def is_enrollment_available(self) -> bool:
        """Check if enrollment is available for this session under any active config."""
        active_configs = self.agenda_item.space.event.get_active_enrollment_configs()
        return any(config.is_session_eligible(self) for config in active_configs)

    @property
    def enrollment_status_context(self) -> dict[str, str | int]:
        """Get context data for enrollment status display in templates."""
        if not self.is_full:
            return {
                "status_type": "not_full",
                "enrolled": self.enrolled_count,
                "limit": self.effective_participants_limit,
            }

        # Session is full - determine why
        if self.is_enrollment_limited:
            return {
                "status_type": "enrollment_limited",
                "enrolled": self.enrolled_count,
                "limit": self.effective_participants_limit,
            }

        return {
            "status_type": "session_full",
            "enrolled": self.enrolled_count,
            "limit": self.participants_limit,
        }

    @property
    def full_participant_info(self) -> str:
        """Get complete participant information display."""
        base_info = f"{self.enrolled_count}/{self.effective_participants_limit}"

        # Add session limit if different from effective limit
        if self.effective_participants_limit != self.participants_limit:
            base_info += f" (session limit: {self.participants_limit})"

        # Add waiting list info
        if self.waiting_count > 0:
            base_info += f", {self.waiting_count} waiting"

        return base_info


class AgendaItemStatus(StrEnum):
    UNASSIGNED = auto()
    UNCONFIRMED = auto()
    CONFIRMED = auto()


class AgendaItem(models.Model):
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, related_name="agenda_items"
    )
    session = models.OneToOneField(
        Session, on_delete=models.CASCADE, related_name="agenda_item"
    )
    session_confirmed = models.BooleanField(default=False)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    class Meta:
        db_table = "agenda_item"
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(start_time__isnull=True)
                    | Q(end_time__isnull=True)
                    | Q(start_time__lt=F("end_time"))
                ),
                name="agenda_item_date_times",
            ),
        )

    def __str__(self) -> str:
        return f"{self.session.title} by {self.session.presenter_name} ({self.status})"

    @property
    def status(self) -> AgendaItemStatus:
        if self.session_confirmed:
            return AgendaItemStatus.CONFIRMED
        return AgendaItemStatus.UNCONFIRMED

    def overlaps_with(self, other_item: AgendaItem) -> bool:
        return bool(
            other_item.start_time
            and other_item.end_time
            and self.start_time
            and self.end_time
            and (
                (other_item.start_time <= self.start_time < other_item.end_time)
                or (other_item.start_time < self.end_time <= other_item.end_time)
            )
        )


class ProposalCategory(models.Model):
    # Owner
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="proposal_categories"
    )
    # ID
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    # Time
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    # Settings
    tag_categories = models.ManyToManyField(TagCategory)
    max_participants_limit = models.PositiveIntegerField(default=100)
    min_participants_limit = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "proposal_category"
        constraints = (
            models.UniqueConstraint(
                fields=("slug", "event"),
                name="proposal_category_has_unique_slug_and_event",
            ),
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


class ProposalStatus(StrEnum):
    CREATED = auto()
    ACCEPTED = auto()
    REJECTED = auto()


class Proposal(models.Model):
    # Owner
    category = models.ForeignKey(
        ProposalCategory, on_delete=models.CASCADE, related_name="proposals"
    )
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name="proposals")
    # ID
    title = models.CharField(max_length=255)
    description = models.TextField(default="", blank=True)
    requirements = models.TextField(blank=True)
    needs = models.TextField(default="", blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    # Preferences
    participants_limit = models.PositiveIntegerField()
    min_age = models.PositiveIntegerField(
        default=0, help_text="Minimum age requirement (0 = no restriction)"
    )
    time_slots = models.ManyToManyField(TimeSlot)
    # Time
    creation_time = models.DateTimeField(auto_now_add=True)
    # Assignment
    session = models.OneToOneField(
        Session,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="proposal",
    )

    class Meta:
        db_table = "proposal"

    def __str__(self) -> str:
        return self.title


class Guild(models.Model):
    """Small group of users for a small club or team."""

    # ID
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(default="", blank=True)
    # Time
    creation_time = models.DateTimeField(auto_now_add=True)
    modification_time = models.DateTimeField(auto_now=True)
    # Settings
    is_public = models.BooleanField(default=True)
    # Members
    members: models.ManyToManyField[User, Never] = models.ManyToManyField(
        User, through="GuildMember"
    )

    class Meta:
        db_table = "guild"
        constraints = (
            models.UniqueConstraint(fields=["slug"], name="guild_unique_slug"),
        )

    def __str__(self) -> str:
        return self.name


class MembershipType(StrEnum):
    APPLIED = auto()
    MEMBER = auto()
    ADMIN = auto()


class GuildMember(models.Model):
    """Membership model for guilds."""

    guild = models.ForeignKey(
        "Guild", on_delete=models.CASCADE, related_name="guild_members"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="guild_members"
    )
    membership_type = models.CharField(
        max_length=255, choices=[(i.value, i.name) for i in MembershipType]
    )

    class Meta:
        db_table = "guild_member"
        constraints = (
            models.UniqueConstraint(
                fields=["guild", "user"], name="guildmember_unique_guild_and_user"
            ),
        )

    def __str__(self) -> str:
        return f"{self.user} ({self.membership_type} in {self.guild})"


class SessionParticipationStatus(StrEnum):
    CONFIRMED = auto()
    WAITING = auto()


class SessionParticipation(models.Model):
    # Owner
    session = models.ForeignKey(
        Session, models.CASCADE, related_name="session_participations"
    )
    user = models.ForeignKey(
        User, models.CASCADE, related_name="session_participations"
    )
    # Time
    creation_time = models.DateTimeField(auto_now_add=True)
    modification_time = models.DateTimeField(auto_now=True)
    # Status
    status = models.CharField(
        max_length=15,
        choices=[(item.value, item.name) for item in SessionParticipationStatus],
    )

    class Meta:
        unique_together = (("session", "user"),)
        db_table = "session_participant"

    def __str__(self) -> str:
        return f"{self.user} {self.status} on {self.session}"
