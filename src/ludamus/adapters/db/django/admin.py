from typing import ClassVar

from django.contrib import admin

from ludamus.adapters.db.django.models import (
    AgendaItem,
    Event,
    Guild,
    Proposal,
    ProposalCategory,
    Session,
    Space,
    Sphere,
    Tag,
    TagCategory,
    TimeSlot,
    User,
)


@admin.register(AgendaItem)
class AgendaItemAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    ...


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, tuple[str]]] = {"slug": ("name",)}


@admin.register(Guild)
class GuildAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, tuple[str]]] = {"slug": ("name",)}


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    ...


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, tuple[str]]] = {"slug": ("name",)}


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, tuple[str]]] = {"slug": ("title",)}


@admin.register(Sphere)
class SphereAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    ...


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    ...


@admin.register(TagCategory)
class TagCategoryAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    ...


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    ...


@admin.register(User)
class UserAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, tuple[str]]] = {"slug": ("name",)}


@admin.register(ProposalCategory)
class ProposalCategoryAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, tuple[str]]] = {"slug": ("name",)}
