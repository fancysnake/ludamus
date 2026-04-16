#!/usr/bin/env python3
"""Seed a robust session proposal form for Playwright end-to-end tests.

Builds out the proposal wizard for the event with open proposals created
by ``bootstrap_data.py``. Adds:

    * EventProposalSettings (anonymous proposals enabled)
    * Several ProposalCategory rows (RPG, Board Game, Workshop, LARP)
    * A variety of PersonalDataField rows (text, select, checkbox; single
      and multiple; with and without free-text "other")
    * A variety of SessionField rows (text, select, checkbox; with icons)
    * TimeSlot rows covering the event window
    * PersonalDataFieldRequirement / SessionFieldRequirement /
      TimeSlotRequirement rows wiring fields to categories with a mix of
      required and optional flags and differing per-category ordering

Run after ``bootstrap_data.py`` (which creates the ``autumn-open`` event
with ``proposals_open=True``). Idempotent — safe to re-run.

Usage:
    mise run _e2e -- python tests/e2e/scripts/bootstrap_proposal_form.py
"""

from __future__ import annotations

import sys
from datetime import datetime, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# pylint: disable=wrong-import-position  # Django imports must follow setup
import django  # noqa: E402

django.setup()

from django.utils.timezone import get_current_timezone  # noqa: E402

from ludamus.adapters.db.django.models import (  # noqa: E402
    Event,
    EventProposalSettings,
    PersonalDataField,
    PersonalDataFieldOption,
    PersonalDataFieldRequirement,
    PersonalDataFieldType,
    ProposalCategory,
    SessionField,
    SessionFieldOption,
    SessionFieldRequirement,
    SessionFieldType,
    TimeSlot,
    TimeSlotRequirement,
)

EVENT_SLUG = "autumn-open"


def _create_personal_fields(event: Event) -> dict[str, PersonalDataField]:
    """Create the catalogue of personal data fields for the event.

    Returns:
        Mapping from field slug to the persisted PersonalDataField.
    """
    specs: list[dict[str, object]] = [
        {
            "slug": "full-name",
            "name": "Full name",
            "question": "What's your full name?",
            "field_type": PersonalDataFieldType.TEXT,
            "max_length": 120,
            "help_text": "We'll show this on the session card.",
            "order": 0,
            "options": [],
        },
        {
            "slug": "phone",
            "name": "Phone number",
            "question": "Mobile number we can reach you on during the event",
            "field_type": PersonalDataFieldType.TEXT,
            "max_length": 30,
            "order": 1,
            "options": [],
        },
        {
            "slug": "experience",
            "name": "Facilitation experience",
            "question": "How many events have you run before?",
            "field_type": PersonalDataFieldType.SELECT,
            "is_multiple": False,
            "order": 2,
            "options": [
                ("First time", "first-time"),
                ("1-3 events", "1-3"),
                ("4-10 events", "4-10"),
                ("More than 10", "10-plus"),
            ],
        },
        {
            "slug": "languages",
            "name": "Languages",
            "question": "Languages you can run your session in",
            "field_type": PersonalDataFieldType.SELECT,
            "is_multiple": True,
            "allow_custom": True,
            "order": 3,
            "options": [
                ("Polski", "pl"),
                ("English", "en"),
                ("Deutsch", "de"),
                ("Français", "fr"),
            ],
        },
        {
            "slug": "dietary",
            "name": "Dietary restrictions",
            "question": "Any dietary restrictions we should know about?",
            "field_type": PersonalDataFieldType.CHECKBOX,
            "is_multiple": True,
            "order": 4,
            "options": [
                ("Vegetarian", "vegetarian"),
                ("Vegan", "vegan"),
                ("Gluten free", "gluten-free"),
                ("Lactose free", "lactose-free"),
                ("Nut allergy", "nut-allergy"),
            ],
        },
        {
            "slug": "bio",
            "name": "Short bio",
            "question": "Tell attendees a bit about yourself",
            "field_type": PersonalDataFieldType.TEXT,
            "max_length": 500,
            "help_text": "Shown publicly on the session page.",
            "is_public": True,
            "order": 5,
            "options": [],
        },
        {
            "slug": "accept-code-of-conduct",
            "name": "Code of conduct",
            "question": "I have read and accept the event code of conduct",
            "field_type": PersonalDataFieldType.CHECKBOX,
            "is_multiple": False,
            "order": 6,
            "options": [],
        },
    ]

    fields: dict[str, PersonalDataField] = {}
    for spec in specs:
        options = spec.pop("options")  # type: ignore[arg-type]
        field, _ = PersonalDataField.objects.update_or_create(
            event=event, slug=spec["slug"], defaults=spec
        )
        for index, (label, value) in enumerate(options):  # type: ignore[assignment]
            PersonalDataFieldOption.objects.update_or_create(
                field=field, value=value, defaults={"label": label, "order": index}
            )
        fields[field.slug] = field
    return fields


def _create_session_fields(event: Event) -> dict[str, SessionField]:
    """Create the catalogue of session fields for the event.

    Returns:
        Mapping from field slug to the persisted SessionField.
    """
    specs: list[dict[str, object]] = [
        {
            "slug": "system",
            "name": "Game system",
            "question": "What system / ruleset / world will you use?",
            "field_type": SessionFieldType.SELECT,
            "is_multiple": False,
            "allow_custom": True,
            "icon": "book-open",
            "is_public": True,
            "order": 0,
            "options": [
                ("Dungeons & Dragons 5e", "dnd5e"),
                ("Call of Cthulhu", "coc"),
                ("Dungeon World", "dungeon-world"),
                ("Blades in the Dark", "blades"),
                ("Fate Core", "fate"),
                ("Homebrew", "homebrew"),
            ],
        },
        {
            "slug": "genre",
            "name": "Genre",
            "question": "Pick all genres that apply",
            "field_type": SessionFieldType.SELECT,
            "is_multiple": True,
            "icon": "film",
            "is_public": True,
            "order": 1,
            "options": [
                ("High fantasy", "high-fantasy"),
                ("Dark fantasy", "dark-fantasy"),
                ("Sci-fi", "sci-fi"),
                ("Cyberpunk", "cyberpunk"),
                ("Post-apocalyptic", "post-apoc"),
                ("Horror", "horror"),
                ("Comedy", "comedy"),
                ("Mystery", "mystery"),
            ],
        },
        {
            "slug": "tone",
            "name": "Tone",
            "question": "What tone should players expect?",
            "field_type": SessionFieldType.SELECT,
            "is_multiple": True,
            "icon": "musical-note",
            "is_public": True,
            "order": 2,
            "options": [
                ("Light-hearted", "light"),
                ("Serious", "serious"),
                ("Gritty", "gritty"),
                ("Absurd", "absurd"),
                ("Romantic", "romantic"),
            ],
        },
        {
            "slug": "triggers",
            "name": "Content warnings",
            "question": "Any content warnings players should know about?",
            "field_type": SessionFieldType.CHECKBOX,
            "is_multiple": True,
            "icon": "exclamation-triangle",
            "is_public": True,
            "order": 3,
            "options": [
                ("Violence", "violence"),
                ("Body horror", "body-horror"),
                ("Death", "death"),
                ("Loss of a loved one", "loss"),
                ("Mental health", "mental-health"),
                ("Spiders / insects", "spiders"),
            ],
        },
        {
            "slug": "complexity",
            "name": "Rules complexity",
            "question": "How crunchy are the rules?",
            "field_type": SessionFieldType.SELECT,
            "is_multiple": False,
            "icon": "chart-bar",
            "is_public": True,
            "order": 4,
            "options": [
                ("Rules-light", "light"),
                ("Medium", "medium"),
                ("Rules-heavy", "heavy"),
            ],
        },
        {
            "slug": "language",
            "name": "Session language",
            "question": "Which language will the session be run in?",
            "field_type": SessionFieldType.SELECT,
            "is_multiple": False,
            "icon": "language",
            "is_public": True,
            "order": 5,
            "options": [("Polski", "pl"), ("English", "en"), ("Deutsch", "de")],
        },
        {
            "slug": "pregens",
            "name": "Pre-generated characters",
            "question": "Do you provide pre-generated characters?",
            "field_type": SessionFieldType.CHECKBOX,
            "is_multiple": False,
            "icon": "user-group",
            "order": 6,
            "options": [],
        },
        {
            "slug": "materials",
            "name": "What players should bring",
            "question": "Anything players should bring with them?",
            "field_type": SessionFieldType.TEXT,
            "max_length": 300,
            "icon": "briefcase",
            "order": 7,
            "options": [],
        },
        {
            "slug": "elevator-pitch",
            "name": "Elevator pitch",
            "question": "One-sentence hook for your session",
            "field_type": SessionFieldType.TEXT,
            "max_length": 200,
            "icon": "megaphone",
            "is_public": True,
            "order": 8,
            "options": [],
        },
    ]

    fields: dict[str, SessionField] = {}
    for spec in specs:
        options = spec.pop("options")  # type: ignore[arg-type]
        field, _ = SessionField.objects.update_or_create(
            event=event, slug=spec["slug"], defaults=spec
        )
        for index, (label, value) in enumerate(options):  # type: ignore[assignment]
            SessionFieldOption.objects.update_or_create(
                field=field, value=value, defaults={"label": label, "order": index}
            )
        fields[field.slug] = field
    return fields


def _create_categories(event: Event) -> dict[str, ProposalCategory]:
    """Create proposal categories with different limits and durations.

    Returns:
        Mapping from category slug to the persisted ProposalCategory.
    """
    specs: list[dict[str, object]] = [
        {
            "slug": "rpg",
            "name": "RPG Session",
            "description": "Tabletop roleplaying games for 3-6 players.",
            "min_participants_limit": 3,
            "max_participants_limit": 6,
            "durations": ["PT2H", "PT3H", "PT4H"],
        },
        {
            "slug": "board-game",
            "name": "Board Game Demo",
            "description": "Teach and play a board game.",
            "min_participants_limit": 2,
            "max_participants_limit": 8,
            "durations": ["PT1H", "PT1H30M", "PT2H"],
        },
        {
            "slug": "workshop",
            "name": "Workshop",
            "description": "Hands-on design, craft or storytelling workshop.",
            "min_participants_limit": 4,
            "max_participants_limit": 20,
            "durations": ["PT1H", "PT2H"],
        },
        {
            "slug": "larp",
            "name": "LARP",
            "description": "Live action roleplay (costume optional).",
            "min_participants_limit": 6,
            "max_participants_limit": 30,
            "durations": ["PT3H", "PT4H"],
        },
    ]

    categories: dict[str, ProposalCategory] = {}
    for spec in specs:
        category, _ = ProposalCategory.objects.update_or_create(
            event=event, slug=spec["slug"], defaults=spec
        )
        categories[category.slug] = category
    return categories


def _create_time_slots(event: Event) -> list[TimeSlot]:
    """Create a handful of time slots covering the event day.

    Returns:
        List of TimeSlot instances in chronological order.
    """
    local_tz = get_current_timezone()
    event_day = event.start_time.astimezone(local_tz).date()
    slot_specs = [
        (time(10, 0), time(12, 0)),
        (time(12, 0), time(14, 0)),
        (time(14, 0), time(16, 0)),
        (time(16, 0), time(18, 0)),
        (time(18, 0), time(20, 0)),
    ]
    slots: list[TimeSlot] = []
    for start, end in slot_specs:
        slot, _ = TimeSlot.objects.get_or_create(
            event=event,
            start_time=datetime.combine(event_day, start, tzinfo=local_tz),
            end_time=datetime.combine(event_day, end, tzinfo=local_tz),
        )
        slots.append(slot)
    return slots


def _wire_personal_requirements(
    categories: dict[str, ProposalCategory], fields: dict[str, PersonalDataField]
) -> None:
    """Attach personal data fields to each category with differing rules."""
    plan: dict[str, list[tuple[str, bool]]] = {
        "rpg": [
            ("full-name", True),
            ("phone", True),
            ("experience", True),
            ("languages", False),
            ("dietary", False),
            ("bio", False),
            ("accept-code-of-conduct", True),
        ],
        "board-game": [
            ("full-name", True),
            ("experience", False),
            ("languages", False),
            ("accept-code-of-conduct", True),
        ],
        "workshop": [
            ("full-name", True),
            ("phone", True),
            ("experience", True),
            ("bio", True),
            ("dietary", False),
            ("accept-code-of-conduct", True),
        ],
        "larp": [
            ("full-name", True),
            ("phone", True),
            ("experience", True),
            ("languages", True),
            ("dietary", True),
            ("bio", True),
            ("accept-code-of-conduct", True),
        ],
    }

    for category_slug, reqs in plan.items():
        category = categories[category_slug]
        for order, (field_slug, is_required) in enumerate(reqs):
            PersonalDataFieldRequirement.objects.update_or_create(
                category=category,
                field=fields[field_slug],
                defaults={"is_required": is_required, "order": order},
            )


def _wire_session_requirements(
    categories: dict[str, ProposalCategory], fields: dict[str, SessionField]
) -> None:
    """Attach session fields to each category with differing rules."""
    plan: dict[str, list[tuple[str, bool]]] = {
        "rpg": [
            ("elevator-pitch", True),
            ("system", True),
            ("genre", True),
            ("tone", False),
            ("triggers", True),
            ("complexity", True),
            ("language", True),
            ("pregens", False),
            ("materials", False),
        ],
        "board-game": [
            ("elevator-pitch", True),
            ("complexity", True),
            ("language", True),
            ("materials", False),
        ],
        "workshop": [
            ("elevator-pitch", True),
            ("language", True),
            ("materials", True),
            ("triggers", False),
        ],
        "larp": [
            ("elevator-pitch", True),
            ("genre", True),
            ("tone", True),
            ("triggers", True),
            ("language", True),
            ("materials", True),
        ],
    }

    for category_slug, reqs in plan.items():
        category = categories[category_slug]
        for order, (field_slug, is_required) in enumerate(reqs):
            SessionFieldRequirement.objects.update_or_create(
                category=category,
                field=fields[field_slug],
                defaults={"is_required": is_required, "order": order},
            )


def _wire_time_slot_requirements(
    categories: dict[str, ProposalCategory], slots: list[TimeSlot]
) -> None:
    """Expose time slots to every category."""
    for category in categories.values():
        for order, slot in enumerate(slots):
            TimeSlotRequirement.objects.update_or_create(
                category=category,
                time_slot=slot,
                defaults={"is_required": False, "order": order},
            )


def main() -> None:
    try:
        event = Event.objects.get(slug=EVENT_SLUG)
    except Event.DoesNotExist:
        print(  # noqa: T201
            f"Event '{EVENT_SLUG}' not found. Run bootstrap_data.py first."
        )
        return

    EventProposalSettings.objects.update_or_create(
        event=event,
        defaults={
            "description": (
                "Pitch a session for the Autumn Open Playtest. "
                "Pick a category, tell us about yourself, then fill in the "
                "session details. Anonymous proposals are welcome."
            ),
            "allow_anonymous_proposals": True,
        },
    )

    personal_fields = _create_personal_fields(event)
    session_fields = _create_session_fields(event)
    categories = _create_categories(event)
    slots = _create_time_slots(event)

    _wire_personal_requirements(categories, personal_fields)
    _wire_session_requirements(categories, session_fields)
    _wire_time_slot_requirements(categories, slots)

    print(  # noqa: T201
        f"Seeded proposal form for '{event.name}': "
        f"{len(categories)} categories, "
        f"{len(personal_fields)} personal fields, "
        f"{len(session_fields)} session fields, "
        f"{len(slots)} time slots."
    )


if __name__ == "__main__":
    main()
