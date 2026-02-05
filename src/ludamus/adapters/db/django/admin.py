from typing import TYPE_CHECKING, Any, ClassVar

from django import forms
from django.contrib import admin

from ludamus.adapters.db.django.models import (
    AgendaItem,
    DomainEnrollmentConfig,
    EnrollmentConfig,
    Event,
    Proposal,
    ProposalCategory,
    Session,
    Space,
    Sphere,
    Tag,
    TagCategory,
    TicketAPIIntegration,
    TimeSlot,
    User,
    UserEnrollmentConfig,
)
from ludamus.adapters.external.ticket_api_registry import get_ticket_api_choices
from ludamus.adapters.security.encryption import SecretEncryption

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.http import HttpRequest


@admin.register(AgendaItem)
class AgendaItemAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    ...


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, Sequence[str]]] = {"slug": ("name",)}


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    ...


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, Sequence[str]]] = {"slug": ("name",)}


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, Sequence[str]]] = {"slug": ("title",)}


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
    list_display = ("name", "user_type", "manager", "email", "discord_username")
    prepopulated_fields: ClassVar[dict[str, Sequence[str]]] = {"slug": ("name",)}


@admin.register(ProposalCategory)
class ProposalCategoryAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    prepopulated_fields: ClassVar[dict[str, Sequence[str]]] = {"slug": ("name",)}


class DomainEnrollmentConfigInline(admin.TabularInline):  # type: ignore [type-arg]
    model = DomainEnrollmentConfig
    extra = 0
    fields = ("domain", "allowed_slots_per_user")


@admin.register(EnrollmentConfig)
class EnrollmentConfigAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    list_display = (
        "event",
        "start_time",
        "end_time",
        "percentage_slots",
        "restrict_to_configured_users",
        "allow_anonymous_enrollment",
    )
    list_filter = (
        "restrict_to_configured_users",
        "allow_anonymous_enrollment",
        "event",
    )
    fields = (
        "event",
        "start_time",
        "end_time",
        "percentage_slots",
        "limit_to_end_time",
        "restrict_to_configured_users",
        "allow_anonymous_enrollment",
        "max_waitlist_sessions",
        "banner_text",
    )


@admin.register(UserEnrollmentConfig)
class UserEnrollmentConfigAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    list_display = (
        "user_email",
        "enrollment_config",
        "allowed_slots",
        "fetched_from_api",
    )
    list_filter = ("fetched_from_api", "enrollment_config__event")
    search_fields = ("user_email",)


@admin.register(DomainEnrollmentConfig)
class DomainEnrollmentConfigAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    list_display = ("domain", "enrollment_config", "allowed_slots_per_user")
    list_filter = ("enrollment_config__event",)
    search_fields = ("domain",)
    fields = ("enrollment_config", "domain", "allowed_slots_per_user")


class TicketAPIIntegrationForm(forms.ModelForm):  # type: ignore [type-arg]
    """Custom form for TicketAPIIntegration with secret field handling."""

    secret = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Enter a new API secret to update, or leave empty to keep existing.",
    )

    class Meta:
        model = TicketAPIIntegration
        fields = ("sphere", "provider", "base_url", "secret", "timeout", "is_active")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Set provider choices from registry
        if choices := get_ticket_api_choices():
            self.fields["provider"].widget = forms.Select(choices=choices)


@admin.register(TicketAPIIntegration)
class TicketAPIIntegrationAdmin(admin.ModelAdmin):  # type: ignore [type-arg]
    """Admin for managing Ticket API integrations per sphere."""

    form = TicketAPIIntegrationForm
    list_display = ("sphere", "provider", "base_url", "is_active", "updated_at")
    list_filter = ("provider", "is_active", "sphere")
    search_fields = ("sphere__name", "base_url")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("sphere", "provider", "base_url", "secret", "timeout")}),
        ("Status", {"fields": ("is_active",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def save_model(
        self,
        request: HttpRequest,
        obj: TicketAPIIntegration,
        form: TicketAPIIntegrationForm,
        change: bool,  # noqa: FBT001
    ) -> None:
        """Encrypt secret before saving."""
        if secret := form.cleaned_data.get("secret"):
            obj.encrypted_secret = SecretEncryption.encrypt(secret)
        super().save_model(request, obj, form, change)
