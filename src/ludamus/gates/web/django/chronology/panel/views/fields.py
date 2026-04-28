"""Field protocols and helpers shared across CFP, proposal, and field views."""

from __future__ import annotations

from typing import (  # pylint: disable=unused-import
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    cast,
)

from ludamus.gates.web.django.chronology.panel.views.base import panel_chrome
from ludamus.pacts import (
    PersonalDataFieldCreateData,
    PersonalDataFieldUpdateData,
    SessionFieldUpdateData,
)

if TYPE_CHECKING:
    from django import forms
    from django.http import QueryDict

    from ludamus.gates.web.django.chronology.panel.views.base import PanelRequest
    from ludamus.pacts import EventDTO


class _FieldDTO(Protocol):
    """Protocol for field DTOs with common attributes."""

    help_text: str
    is_public: bool
    max_length: int
    pk: int
    name: str
    question: str


def field_initial(field: _FieldDTO) -> dict[str, Any]:
    """Return the initial form values shared by personal-data and session fields.

    Returns:
        Mapping with ``name``, ``question``, ``max_length``, ``help_text``,
        ``is_public`` keys.
    """
    return {
        "name": field.name,
        "question": field.question,
        "max_length": field.max_length,
        "help_text": field.help_text,
        "is_public": field.is_public,
    }


def personal_data_field_update_payload(
    form: forms.Form, options: list[str] | None
) -> PersonalDataFieldUpdateData:
    """Build the typed update payload for a personal-data field.

    Returns:
        A ``PersonalDataFieldUpdateData`` populated from form fields.
    """
    return PersonalDataFieldUpdateData(
        name=form.cleaned_data["name"],
        question=form.cleaned_data["question"],
        max_length=form.cleaned_data.get("max_length") or 0,
        help_text=form.cleaned_data.get("help_text") or "",
        is_public=form.cleaned_data.get("is_public", False),
        options=options,
    )


def session_field_update_payload(
    form: forms.Form, options: list[str] | None
) -> SessionFieldUpdateData:
    """Build the typed update payload for a session field.

    Returns:
        A ``SessionFieldUpdateData`` populated from form fields.
    """
    return SessionFieldUpdateData(
        name=form.cleaned_data["name"],
        question=form.cleaned_data["question"],
        max_length=form.cleaned_data.get("max_length") or 0,
        help_text=form.cleaned_data.get("help_text") or "",
        icon=form.cleaned_data.get("icon") or "",
        is_public=form.cleaned_data.get("is_public", False),
        options=options,
    )


def parse_field_form_data(form: forms.Form) -> PersonalDataFieldCreateData:
    field_type = cast(
        "Literal['text', 'select', 'checkbox']",
        form.cleaned_data.get("field_type") or "text",
    )
    options_text = form.cleaned_data.get("options") or ""
    options = [o.strip() for o in options_text.split("\n") if o.strip()] or None
    return PersonalDataFieldCreateData(
        name=form.cleaned_data["name"],
        question=form.cleaned_data["question"],
        field_type=field_type,
        options=options,
        is_multiple=form.cleaned_data.get("is_multiple") or False,
        allow_custom=form.cleaned_data.get("allow_custom") or False,
        max_length=form.cleaned_data.get("max_length") or 0,
        help_text=form.cleaned_data.get("help_text") or "",
        is_public=form.cleaned_data.get("is_public") or False,
    )


def sort_fields_by_order[T: _FieldDTO](fields: list[T], order: list[int]) -> list[T]:
    """Sort fields by saved order, with unordered fields at the end.

    Args:
        fields: List of field DTOs to sort.
        order: List of field PKs defining the order.

    Returns:
        Sorted list of fields.
    """
    if not order:
        return fields
    order_map = {fid: idx for idx, fid in enumerate(order)}
    for idx, field in enumerate(fields):
        if field.pk not in order_map:
            order_map[field.pk] = len(order) + idx
    return sorted(fields, key=lambda f: order_map[f.pk])


def field_edit_context(
    request: PanelRequest,
    event: EventDTO,
    field: _FieldDTO,
    form: forms.Form,
    category_pks: dict[str, set[int]],
) -> dict[str, Any]:
    """Build the shared template context for field create/edit pages.

    ``category_pks`` is the dict returned by ``category_requirements_context``
    (or a similarly-shaped fallback for the GET path).

    Returns:
        Mapping that includes ``panel_chrome``, the field, the form, the
        proposal categories list, and the selected category-pk sets.
    """
    return {
        **panel_chrome(request, event),
        "active_nav": "cfp",
        "field": field,
        "form": form,
        "categories": request.di.uow.proposal_categories.list_by_event(event.pk),
        **category_pks,
    }


def category_requirements_context(post: QueryDict) -> dict[str, set[int]]:
    """Build the required/optional category-pk sets for field-edit re-renders.

    Returns:
        Mapping with ``required_category_pks`` and ``optional_category_pks``
        sets, ready to merge into a template context.
    """
    cat_reqs, _order = parse_field_requirements(post, "category_", "category_order")
    return {
        "required_category_pks": {pk for pk, is_req in cat_reqs.items() if is_req},
        "optional_category_pks": {pk for pk, is_req in cat_reqs.items() if not is_req},
    }


def parse_field_requirements(
    post_data: QueryDict, prefix: str, order_key: str
) -> tuple[dict[int, bool], list[int]]:
    """Parse field requirements and order from POST data.

    Args:
        post_data: The POST data from the request.
        prefix: The field prefix (e.g., "field_" or "session_field_").
        order_key: The key for the order field (e.g., "field_order").

    Returns:
        Tuple of (requirements dict mapping field_id to is_required, order list).
    """
    requirements: dict[int, bool] = {}
    for key, value in post_data.items():
        if key.startswith(prefix) and value in {"required", "optional"}:
            field_id = int(key.removeprefix(prefix))
            requirements[field_id] = value == "required"
    order_raw = post_data.get(order_key, "")
    order = [int(x) for x in order_raw.split(",") if x.strip()]
    return requirements, order
