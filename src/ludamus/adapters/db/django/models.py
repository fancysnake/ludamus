from __future__ import annotations

import math
from contextlib import suppress
from datetime import UTC, datetime
from enum import StrEnum, auto
from functools import partial
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any, ClassVar, Never, Protocol

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, models
from django.db.models import F, Q, QuerySet
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable

    from django.db.models.expressions import Combinable

MAX_SLUG_RETRIES = 10
RANDOM_SLUG_BYTES = 7  # 10 characters


class ModelWithSlug(Protocol):
    slug: models.SlugField[str | int | Combinable, str]


def save_with_slugified_name(
    *, instance: ModelWithSlug, name: str, save: Callable[[], None]
) -> None:
    base_slug = slugify(name)[:47]
    instance.slug = base_slug  # type: ignore [assignment]
    for __ in range(MAX_SLUG_RETRIES):
        with suppress(IntegrityError):
            save()
            return

        instance.slug = f"{base_slug}-{token_urlsafe(1)}"  # type: ignore [assignment]

    save()


class User(AbstractBaseUser, PermissionsMixin):
    EMAIL_FIELD = "email"
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: ClassVar = ["email"]

    class UserType(models.TextChoices):
        ACTIVE = "active", _("Active")
        CONNECTED = "connected", _("Connected")

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
        return self.name or "Andrzej"

    def get_short_name(self) -> str:
        return self.name.split(" ")[0]

    def email_user(  # type: ignore [explicit-any]
        self,
        subject: str,
        message: str,
        from_email: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        send_mail(subject, message, from_email, [self.email], **kwargs)

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

    def save(  # pylint: disable=arguments-differ
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        save_with_slugified_name(
            instance=self,
            name=self.name,
            save=partial(
                super().save,
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            ),
        )

    @property
    def age(self) -> int:
        if self.birth_date:
            return math.floor(
                (datetime.now(tz=UTC).date() - self.birth_date).days / 365.25
            )

        return 0


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
    # Enrollment times
    enrollment_start_time = models.DateTimeField(blank=True, null=True)
    enrollment_end_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "event"
        constraints = (
            models.UniqueConstraint(
                fields=("sphere", "slug"), name="event_has_unique_slug_and_sphere"
            ),
            models.CheckConstraint(
                check=Q(
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

    def save(  # pylint: disable=arguments-differ
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        save_with_slugified_name(
            instance=self,
            name=self.name,
            save=partial(
                super().save,
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            ),
        )

    @property
    def is_enrollment_active(self) -> bool:
        return (
            self.enrollment_start_time is not None
            and self.enrollment_end_time is not None
            and (
                self.enrollment_start_time
                < datetime.now(tz=UTC)
                < self.enrollment_end_time
            )
        )

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

    def agenda_items(self) -> QuerySet[AgendaItem]:
        return AgendaItem.objects.filter(space__event=self)


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

    def save(  # pylint: disable=arguments-differ
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        save_with_slugified_name(
            instance=self,
            name=self.name,
            save=partial(
                super().save,
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            ),
        )


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
                check=Q(start_time__lt=F("end_time")), name="timeslot_date_times"
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
    class InputType(models.TextChoices):
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


class SessionStatus(StrEnum):
    DRAFT = auto()
    PLANNED = auto()
    PUBLISHED = auto()
    ONGOING = auto()
    PAST = auto()


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
    host = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="hosted_sessions"
    )
    # ID
    title = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(default="", blank=True)
    requirements = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    # Time
    creation_time = models.DateTimeField(auto_now_add=True)
    modification_time = models.DateTimeField(auto_now=True)
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    publication_time = models.DateTimeField(blank=True, null=True)
    # Participants
    participants_limit = models.PositiveIntegerField()
    participants: models.ManyToManyField[User, Never] = models.ManyToManyField(
        User, through="SessionParticipation"
    )

    class Meta:
        db_table = "session"
        constraints = (
            models.UniqueConstraint(
                fields=["slug", "sphere"], name="session_unique_slug_in_sphere"
            ),
            models.CheckConstraint(
                check=(
                    (
                        Q(publication_time__isnull=True)
                        | Q(start_time__isnull=True)
                        | Q(publication_time__lte=F("start_time"))
                    )
                    & (
                        Q(start_time__isnull=True)
                        | Q(end_time__isnull=True)
                        | Q(start_time__lt=F("end_time"))
                    )
                ),
                name="session_date_times",
            ),
        )

    def __str__(self) -> str:
        return self.title

    def save(  # pylint: disable=arguments-differ
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        save_with_slugified_name(
            instance=self,
            name=self.title,
            save=partial(
                super().save,
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            ),
        )

    @property
    def status(self) -> SessionStatus:
        now = datetime.now(tz=UTC)
        if not self.start_time or not self.end_time or not self.publication_time:
            return SessionStatus.DRAFT
        if now < self.publication_time:
            return SessionStatus.PLANNED
        if now < self.start_time:
            return SessionStatus.PUBLISHED
        if now < self.end_time:
            return SessionStatus.ONGOING
        return SessionStatus.PAST


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

    class Meta:
        db_table = "agenda_item"

    def __str__(self) -> str:
        return f"{self.session.title} by {self.session.host.name} ({self.status})"

    @property
    def status(self) -> AgendaItemStatus:
        if self.session_confirmed:
            return AgendaItemStatus.CONFIRMED
        return AgendaItemStatus.UNCONFIRMED


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

    def save(  # pylint: disable=arguments-differ
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        save_with_slugified_name(
            instance=self,
            name=self.name,
            save=partial(
                super().save,
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            ),
        )


class ProposalStatus(StrEnum):
    CREATED = auto()
    ACCEPTED = auto()
    REJECTED = auto()


class Proposal(models.Model):
    # Owner
    proposal_category = models.ForeignKey(
        ProposalCategory, on_delete=models.CASCADE, related_name="proposals"
    )
    host = models.ForeignKey(
        User, on_delete=models.CASCADE, blank=True, null=True, related_name="proposals"
    )
    # ID
    title = models.CharField(max_length=255)
    description = models.TextField(default="", blank=True)
    requirements = models.TextField(blank=True)
    needs = models.TextField(default="", blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    # Preferences
    participants_limit = models.PositiveIntegerField()
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

    def save(  # pylint: disable=arguments-differ
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        save_with_slugified_name(
            instance=self,
            name=self.name,
            save=partial(
                super().save,
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            ),
        )


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
