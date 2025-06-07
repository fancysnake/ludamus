from __future__ import annotations

from enum import StrEnum, auto
from typing import TYPE_CHECKING, Never, TypedDict

from django.contrib.auth.models import AbstractUser
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, JSONField, Q, QuerySet
from django.utils import timezone
from django.utils.text import slugify
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable


class User(AbstractUser):
    id = models.UUIDField(primary_key=True)

    class Meta:
        db_table = "crowd_user"


class Auth0User(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vendor = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255)

    class Meta:
        db_table = "crowd_auth0_user"

    def __str__(self) -> str:
        return f"{self.vendor}|{self.external_id}"


def default_sphere_settings() -> dict[str, list[str] | dict[str, str]]:
    return {"theme": {}, "forms": []}


class Sphere(models.Model):
    """Big group for whole provinces, topics, organizations or big events."""

    is_open = models.BooleanField(default=True, verbose_name=_("is open"))
    managers = models.ManyToManyField(User, verbose_name=_("managers"))
    name = models.CharField(max_length=255, verbose_name=_("name"))
    settings = JSONField(default=default_sphere_settings)
    site = models.OneToOneField(
        Site, on_delete=models.PROTECT, related_name="sphere", verbose_name=_("site")
    )

    class Meta:
        db_table = "nb_sphere"
        verbose_name = _("sphere")
        verbose_name_plural = _("spheres")

    def __str__(self) -> str:
        return self.name


def default_festival_settings() -> dict[str, list[str] | dict[str, str]]:
    return {"theme": {}, "forms": []}


class FestivalStatus(StrEnum):
    DRAFT = auto()
    READY = auto()
    PROPOSAL = auto()
    AGENDA = auto()
    AGENDA_PROPOSAL = auto()
    ONGOING = auto()
    PAST = auto()


class Festival(models.Model):

    start_time = models.DateTimeField(
        blank=True, null=True, verbose_name=_("start time")
    )
    end_time = models.DateTimeField(blank=True, null=True, verbose_name=_("end time"))
    name = models.CharField(max_length=255, verbose_name=_("name"))
    settings = JSONField(default=default_festival_settings, verbose_name=_("settings"))
    slug = models.SlugField(verbose_name=_("slug"))
    sphere = models.ForeignKey(
        Sphere, on_delete=models.CASCADE, verbose_name=_("sphere")
    )
    start_proposal = models.DateTimeField(
        blank=True, null=True, verbose_name=_("start proposal")
    )
    end_proposal = models.DateTimeField(
        blank=True, null=True, verbose_name=_("end proposal")
    )
    start_publication = models.DateTimeField(
        blank=True, null=True, verbose_name=_("start publication")
    )

    class Meta:
        db_table = "ch_festival"
        verbose_name = _("festival")
        verbose_name_plural = _("festivals")
        constraints = (
            models.UniqueConstraint(
                fields=("sphere", "slug"), name="festival_has_unique_slug_and_sphere"
            ),
            models.CheckConstraint(
                check=Q(
                    start_proposal__isnull=True,
                    end_proposal__isnull=True,
                    start_publication__isnull=True,
                    start_time__isnull=True,
                    end_time__isnull=True,
                )
                | Q(
                    start_proposal__lte=F("end_proposal"),
                    start_publication__lte=F("start_time"),
                    start_time__lt=F("end_time"),
                ),
                name="festival_date_times",
            ),
        )

    def __str__(self) -> str:
        return self.name

    @property
    def status(self) -> FestivalStatus:
        if (
            self.start_time
            and self.end_time
            and self.start_proposal
            and self.end_proposal
            and self.start_publication
        ):
            now = timezone.now()
            status_mapping = (
                (self.start_proposal, FestivalStatus.READY),
                (self.start_publication, FestivalStatus.PROPOSAL),
                (self.end_proposal, FestivalStatus.AGENDA_PROPOSAL),
                (self.start_time, FestivalStatus.AGENDA),
                (self.end_time, FestivalStatus.ONGOING),
            )
            for key, value in status_mapping:
                if now < key:
                    return value
            return FestivalStatus.PAST
        return FestivalStatus.DRAFT

    def agenda_items(self) -> QuerySet[AgendaItem]:
        return AgendaItem.objects.filter(room__festival=self)


class Room(models.Model):
    festival = models.ForeignKey(
        Festival,
        on_delete=models.CASCADE,
        verbose_name=_("festival"),
        related_name="rooms",
    )
    name = models.CharField(max_length=255, verbose_name=_("name"))
    slug = models.SlugField(verbose_name=_("slug"))

    class Meta:
        db_table = "ch_room"
        verbose_name = _("room")
        verbose_name_plural = _("rooms")
        constraints = (
            models.UniqueConstraint(
                fields=("slug", "festival"), name="room_has_unique_slug_and_festival"
            ),
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


class TimeSlot(models.Model):
    end_time = models.DateTimeField(verbose_name=_("end time"))
    start_time = models.DateTimeField(verbose_name=_("start time"))
    festival = models.ForeignKey(
        Festival,
        on_delete=models.CASCADE,
        verbose_name=_("festival"),
        related_name="time_slots",
    )

    class Meta:
        db_table = "ch_time_slot"
        verbose_name = _("time slot")
        verbose_name_plural = _("time slots")
        constraints = (
            models.UniqueConstraint(
                fields=("festival", "start_time", "end_time"),
                name="timeslot_has_unique_times_for_festival",
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

    def save(
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        self.full_clean()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def validate_unique(self, exclude: Collection[str] | None = None) -> None:
        super().validate_unique(exclude)
        festival_slots = TimeSlot.objects.filter(festival=self.festival)
        conflicted = festival_slots.filter(
            Q(start_time__gt=self.start_time, start_time__lt=self.end_time)
            | Q(end_time__gt=self.start_time, end_time__lt=self.end_time)
            | Q(start_time__lte=self.start_time, end_time__gte=self.end_time)
        ).last()
        if conflicted and conflicted != self:
            raise ValidationError(_("Time slots can't overlap!"))


class DescribedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
    description = models.TextField(
        default="", blank=True, verbose_name=_("description")
    )
    name = models.CharField(max_length=255, verbose_name=_("name"))
    slug = models.SlugField(verbose_name=_("slug"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))

    objects = models.Manager()

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.name

    def save(
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self.slug:
            self.slug = self._get_unique_slug()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def _get_unique_slug(self, *unique_within: str) -> str:
        base_slug = str(slugify(self.name))[:48]
        slug = base_slug
        i = 1
        unique_kwargs = {key: getattr(self, key) for key in unique_within}
        while self.__class__.objects.filter(slug=slug, **unique_kwargs).exists():
            slug = f"{base_slug}-{i}"
            i += 1
        return slug


class MeetingStatus(StrEnum):
    DRAFT = auto()
    PLANNED = auto()
    PUBLISHED = auto()
    ONGOING = auto()
    PAST = auto()


class Meeting(DescribedModel):
    """Meeting model."""

    end_time = models.DateTimeField(blank=True, null=True, verbose_name=_("end time"))
    guild = models.ForeignKey(
        "Guild",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        verbose_name=_("guild"),
    )
    image = models.ImageField(null=True, blank=True, verbose_name=_("image"))
    location = models.TextField(blank=True, default="", verbose_name=_("location"))
    meeting_url = models.URLField(blank=True, verbose_name=_("meeting url"))
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="organized_meetings",
        verbose_name=_("organizer"),
    )
    participants: models.ManyToManyField[User, Never] = models.ManyToManyField(
        User,
        related_name="participated_meetings",
        verbose_name=_("participants"),
        through="MeetingParticipant",
    )
    participants_limit = models.IntegerField(
        blank=True, null=True, default=0, verbose_name=_("participants limit")
    )
    publication_time = models.DateTimeField(
        blank=True, null=True, verbose_name=_("publication time")
    )
    sphere = models.ForeignKey(
        "Sphere", on_delete=models.CASCADE, verbose_name=_("sphere")
    )
    start_time = models.DateTimeField(
        blank=True, null=True, verbose_name=_("start time")
    )

    class Meta:
        db_table = "nb_meeting"
        verbose_name = _("meeting")
        verbose_name_plural = _("meetings")
        constraints = (
            models.UniqueConstraint(
                fields=["slug", "sphere"], name="meeting_unique_slug_in_sphere"
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
                name="meeting_date_times",
            ),
        )

    def save(
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self.slug:
            self.slug = self._get_unique_slug("sphere")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @property
    def status(self) -> MeetingStatus:
        now = timezone.now()
        if not self.start_time or not self.end_time or not self.publication_time:
            return MeetingStatus.DRAFT
        if now < self.publication_time:
            return MeetingStatus.PLANNED
        if now < self.start_time:
            return MeetingStatus.PUBLISHED
        if now < self.end_time:
            return MeetingStatus.ONGOING
        return MeetingStatus.PAST


class AgendaItemStatus(StrEnum):
    UNASSIGNED = auto()
    UNCONFIRMED = auto()
    CONFIRMED = auto()


class AgendaItem(models.Model):
    meeting = models.OneToOneField(
        Meeting,
        on_delete=models.CASCADE,
        verbose_name=_("meeting"),
        related_name="agenda_item",
    )
    meeting_confirmed = models.BooleanField(
        default=False, verbose_name=_("meeting confirmed")
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        verbose_name=_("room"),
        related_name="agenda_item",
    )

    class Meta:
        db_table = "ch_agenda_item"
        verbose_name = _("agenda item")
        verbose_name_plural = _("agenda items")

    def __str__(self) -> str:
        return (
            f"{self.meeting.name} by {self.meeting.proposal.speaker_name} "
            f"({self.status})"
        )

    @property
    def status(self) -> AgendaItemStatus:
        if self.meeting_confirmed:
            return AgendaItemStatus.CONFIRMED
        return AgendaItemStatus.UNCONFIRMED


class WaitList(models.Model):
    festival = models.ForeignKey(
        Festival, on_delete=models.CASCADE, verbose_name=_("festival")
    )
    name = models.CharField(max_length=255, verbose_name=_("name"))
    slug = models.SlugField(verbose_name=_("slug"))

    class Meta:
        db_table = "ch_wait_list"
        verbose_name = _("waitlist")
        verbose_name_plural = _("waitlists")
        constraints = (
            models.UniqueConstraint(
                fields=("slug", "festival"),
                name="waitlist_has_unique_slug_and_festival",
            ),
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


class EmptyDict(TypedDict):
    pass


def default_json_field() -> EmptyDict:
    return {}


class Proposal(models.Model):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    STATUS_CHOICES = (
        (CREATED, _("Created")),
        (ACCEPTED, _("Accepted")),
        (REJECTED, _("Rejected")),
    )

    name = models.CharField(max_length=255, verbose_name=_("name"))
    description = models.TextField(
        default="", blank=True, verbose_name=_("description")
    )
    duration_minutes = models.PositiveIntegerField(verbose_name=_("duration minutes"))
    city = models.CharField(
        max_length=255, default="", blank=True, verbose_name=_("city")
    )
    club = models.CharField(
        max_length=255, default="", blank=True, verbose_name=_("club")
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default=CREATED, verbose_name=_("status")
    )
    meeting = models.OneToOneField(
        Meeting,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("meeting"),
        related_name="proposal",
    )
    needs = models.TextField(default="", blank=True, verbose_name=_("needs"))
    other_contact = JSONField(
        blank=True, default=default_json_field, verbose_name=_("other contact")
    )
    other_data = JSONField(
        blank=True, default=default_json_field, verbose_name=_("other data")
    )
    phone = models.CharField(
        max_length=255, default="", blank=True, verbose_name=_("phone")
    )
    time_slots = models.ManyToManyField(TimeSlot, verbose_name=_("time slots"))
    waitlist = models.ForeignKey(
        WaitList, on_delete=models.CASCADE, verbose_name=_("waitlist")
    )
    speaker_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="proposals",
        blank=True,
        null=True,
        verbose_name=_("speaker user"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
    speaker_name = models.CharField(max_length=255, verbose_name=_("speaker name"))
    topic = models.CharField(
        max_length=255, default="", blank=True, verbose_name=_("topic")
    )

    class Meta:
        db_table = "ch_proposal"
        verbose_name = _("proposal")
        verbose_name_plural = _("proposals")

    def __str__(self) -> str:
        return self.name


class Guild(DescribedModel):
    """Small group of users for a small club or team."""

    is_public = models.BooleanField(default=True, verbose_name=_("is public"))
    members: models.ManyToManyField[User, Never] = models.ManyToManyField(
        User, through="GuildMember", verbose_name=_("members")
    )

    class Meta:
        db_table = "nb_guild"
        verbose_name = _("guild")
        verbose_name_plural = _("guilds")
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
        "Guild", on_delete=models.CASCADE, verbose_name=_("guild")
    )
    membership_type = models.CharField(
        max_length=255,
        choices=[(i.value, i.name) for i in MembershipType],
        verbose_name=_("membership type"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"))

    class Meta:
        db_table = "nb_guild_member"
        verbose_name = _("guild member")
        verbose_name_plural = _("guild members")
        constraints = (
            models.UniqueConstraint(
                fields=["guild", "user"], name="guildmember_unique_guild_and_user"
            ),
        )

    def __str__(self) -> str:
        return f"{self.user} ({self.membership_type} in {self.guild})"


class MeetingParticipationStatus(StrEnum):
    CONFIRMED = auto()
    WAITING = auto()


class MeetingParticipant(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
    meeting = models.ForeignKey(Meeting, models.CASCADE)
    status = models.CharField(
        max_length=15,
        choices=[(item.value, item.name) for item in MeetingParticipationStatus],
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))
    user = models.ForeignKey(User, models.CASCADE)

    class Meta:
        unique_together = (("meeting", "user"),)
        db_table = "nb_meeting_participant"

    def __str__(self) -> str:
        return f"{self.user} {self.status} on {self.meeting}"
