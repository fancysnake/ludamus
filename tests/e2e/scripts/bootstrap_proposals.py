"""Seed data for visualizing the proposals management feature.

Creates an event with active CFP, personal data fields, session fields,
multiple proposal categories, and 25 proposals in various states
(pending, rejected, accepted/unassigned, accepted/scheduled).

Usage:
    mise run dj shell < tests/e2e/scripts/bootstrap_proposals.py
    # or
    python tests/e2e/scripts/bootstrap_proposals.py
"""

from __future__ import annotations

import logging
import os
import random
import sys
from datetime import timedelta
from pathlib import Path

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ludamus.edges.settings")

# pylint: disable=wrong-import-position  # Django imports must be after setup
import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth.hashers import make_password  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from django.utils import timezone  # noqa: E402

from ludamus.adapters.db.django.models import (  # noqa: E402
    AgendaItem,
    Area,
    Event,
    PersonalDataField,
    PersonalDataFieldOption,
    PersonalDataFieldRequirement,
    Proposal,
    ProposalCategory,
    Session,
    SessionField,
    SessionFieldOption,
    SessionFieldRequirement,
    Space,
    Sphere,
    Tag,
    TagCategory,
    TimeSlot,
    Venue,
)

User = django.contrib.auth.get_user_model()

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

HOST_DATA = [
    ("anna_gm", "Anna Kowalska", "anna@example.com"),
    ("marek_dm", "Marek Nowak", "marek@example.com"),
    ("julia_rpg", "Julia Wiśniewska", "julia@example.com"),
    ("tomek_board", "Tomasz Zieliński", "tomek@example.com"),
    ("kasia_larp", "Katarzyna Wójcik", "kasia@example.com"),
    ("piotr_strat", "Piotr Kamiński", "piotr@example.com"),
    ("ola_story", "Aleksandra Lewandowska", "ola@example.com"),
]

PROPOSALS = [
    # (title, description, host_index, category_slug, status,
    #  needs, requirements, min_age, participants_limit)
    (
        "Dungeons of Dread",
        (
            "Classic dungeon crawl with pre-made characters. "
            "Expect traps, treasure, and terrible decisions."
        ),
        0,
        "rpg",
        "pending",
        "Battle map, miniatures",
        "None - beginners welcome!",
        0,
        6,
    ),
    (
        "Cyberpunk RED: Night City Stories",
        "Explore the dark streets of Night City in this one-shot adventure.",
        1,
        "rpg",
        "pending",
        "Character sheets provided",
        "Basic RPG knowledge helpful",
        16,
        5,
    ),
    (
        "Fate Condensed: Pulp Adventures",
        "Indiana Jones meets H.P. Lovecraft in this fast-paced Fate game.",
        2,
        "rpg",
        "pending",
        "",
        "None",
        12,
        6,
    ),
    (
        "Blades in the Dark: The Last Score",
        "You are a crew of daring scoundrels seeking fortune on the haunted streets.",
        0,
        "rpg",
        "rejected",
        "Pre-gen characters available",
        "",
        14,
        4,
    ),
    (
        "Call of Cthulhu: The Haunting",
        "Classic introductory scenario for new investigators.",
        3,
        "rpg",
        "pending",
        "",
        "No experience needed",
        16,
        6,
    ),
    (
        "Mausritter: The Great Cheese Heist",
        "Tiny mice on a big adventure. Family-friendly OSR fun.",
        2,
        "rpg",
        "scheduled",
        "",
        "",
        0,
        8,
    ),
    (
        "Settlers of Catan Tournament",
        "Competitive 4-player Catan with tournament brackets.",
        4,
        "board",
        "pending",
        "Game provided",
        "",
        10,
        16,
    ),
    (
        "Wingspan Marathon",
        "Play through multiple rounds of the award-winning bird game.",
        5,
        "board",
        "pending",
        "All expansions included",
        "",
        0,
        8,
    ),
    (
        "Gloomhaven: Jaws of the Lion Intro",
        "Learn the basics of Gloomhaven in a guided introductory scenario.",
        3,
        "board",
        "unassigned",
        "Game provided, no prep needed",
        "Patience for a 2h+ game",
        12,
        4,
    ),
    (
        "Twilight Imperium: Abridged",
        "A streamlined 4-hour TI4 experience. Yes, really.",
        5,
        "board",
        "rejected",
        "Snacks recommended",
        "Experience with heavy games",
        14,
        6,
    ),
    (
        "Azul: Speed Tournament",
        "Quick-fire Azul rounds with Swiss-system pairings.",
        4,
        "board",
        "pending",
        "",
        "",
        8,
        12,
    ),
    (
        "Pandemic Legacy Season 0",
        "Cold War spy thriller cooperative campaign.",
        1,
        "board",
        "scheduled",
        "",
        "Commit to the full campaign",
        14,
        4,
    ),
    (
        "Werewolf: Ultimate Night",
        "Large-group social deduction at its finest.",
        6,
        "party",
        "pending",
        "Moderator provided",
        "",
        12,
        20,
    ),
    (
        "Codenames Tournament",
        "Team-based word association competition.",
        4,
        "party",
        "pending",
        "",
        "",
        10,
        16,
    ),
    (
        "The Resistance: Avalon Marathon",
        "Multiple rounds of hidden roles and deception.",
        6,
        "party",
        "rejected",
        "",
        "",
        12,
        10,
    ),
    (
        "Dixit: Storytelling Edition",
        "Creative image interpretation with house rules.",
        2,
        "party",
        "pending",
        "",
        "Imagination required!",
        8,
        8,
    ),
    (
        "Introduction to LARP Combat",
        "Learn the basics of foam sword fighting and LARP etiquette.",
        4,
        "workshop",
        "pending",
        "Foam weapons provided",
        "Comfortable shoes",
        16,
        15,
    ),
    (
        "Miniature Painting 101",
        "Learn to paint your first miniature. All supplies provided.",
        3,
        "workshop",
        "scheduled",
        "Paints and brushes included",
        "Bring an old shirt!",
        10,
        10,
    ),
    (
        "Game Design Workshop: Prototyping",
        "Turn your game idea into a playable prototype in 2 hours.",
        5,
        "workshop",
        "pending",
        "Card stock, markers, dice provided",
        "",
        14,
        8,
    ),
    (
        "World-Building for GMs",
        "Techniques for creating compelling campaign settings.",
        0,
        "workshop",
        "unassigned",
        "Notebook recommended",
        "",
        0,
        12,
    ),
    (
        "D&D 5e: Lost Mine of Phandelver",
        "The classic starter adventure, chapters 1-2.",
        1,
        "rpg",
        "pending",
        "Pre-gen characters",
        "New players preferred",
        10,
        5,
    ),
    (
        "Mothership: Dead Planet",
        "Sci-fi horror survival. Not everyone will make it.",
        0,
        "rpg",
        "pending",
        "",
        "Mature themes",
        18,
        5,
    ),
    (
        "Root: The Woodland Alliance",
        "Asymmetric woodland warfare. Learn all four factions.",
        5,
        "board",
        "pending",
        "Game provided",
        "",
        10,
        4,
    ),
    (
        "Mysterium: Ghost Stories",
        "Cooperative deduction with surreal dream visions.",
        6,
        "board",
        "pending",
        "",
        "",
        10,
        7,
    ),
    (
        "Fiasco: Hollywood Disaster",
        "No GM needed - collaborative storytelling about ambitious plans going wrong.",
        2,
        "rpg",
        "rejected",
        "",
        "",
        16,
        5,
    ),
]

TAG_CATEGORIES_DATA = [
    (
        "Genre",
        "tag",
        [
            "Fantasy",
            "Sci-Fi",
            "Horror",
            "Historical",
            "Modern",
            "Comedy",
            "Mystery",
            "Post-Apocalyptic",
        ],
    ),
    ("Complexity", "signal", ["Beginner", "Intermediate", "Advanced", "Expert"]),
    ("Language", "language", ["Polish", "English", "Bilingual"]),
]


def _get_or_create_sphere() -> tuple[Site, Sphere]:
    root_domain = os.environ.get("ROOT_DOMAIN", settings.ROOT_DOMAIN)
    site, _ = Site.objects.get_or_create(
        domain=root_domain, defaults={"name": root_domain}
    )
    sphere, _ = Sphere.objects.get_or_create(site=site, defaults={"name": site.name})
    return site, sphere


def _create_manager(sphere: Sphere) -> User:
    manager, created = User.objects.get_or_create(
        username="panel_admin",
        defaults={
            "name": "Panel Admin",
            "email": "admin@example.com",
            "slug": "panel-admin",
            "user_type": "active",
            "is_active": True,
            "password": make_password("admin123"),
        },
    )
    sphere.managers.add(manager)
    if created:
        log.info("Created manager: %s (password: admin123)", manager.username)
    else:
        log.info("Manager exists: %s", manager.username)
    return manager


def _create_hosts() -> list:
    hosts = []
    for username, name, email in HOST_DATA:
        host, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "name": name,
                "email": email,
                "slug": username,
                "user_type": "active",
                "is_active": True,
                "password": make_password(None),
            },
        )
        hosts.append(host)
    return hosts


def _create_event(sphere: Sphere) -> Event:
    now = timezone.now()
    event, created = Event.objects.get_or_create(
        slug="tabletop-fest-2026",
        defaults={
            "sphere": sphere,
            "name": "Tabletop Fest 2026",
            "description": (
                "The biggest tabletop gaming event of the year!\n\n"
                "Three days of RPGs, board games, workshops, and fun. "
                "Whether you're a veteran GM or picking up dice for the first time, "
                "there's a table waiting for you."
            ),
            "start_time": now + timedelta(days=14),
            "end_time": now + timedelta(days=14, hours=10),
            "proposal_start_time": now - timedelta(days=30),
            "proposal_end_time": now + timedelta(days=7),
            "publication_time": now - timedelta(days=35),
        },
    )
    if created:
        log.info("Created event: %s", event.name)
    else:
        log.info("Event exists: %s", event.name)
    return event


def _create_categories(event: Event) -> dict[str, ProposalCategory]:
    now = timezone.now()
    categories_data = [
        ("RPG Session", "rpg", now - timedelta(days=30), now + timedelta(days=7)),
        ("Board Game", "board", now - timedelta(days=30), now + timedelta(days=7)),
        ("Party Game", "party", now - timedelta(days=20), now + timedelta(days=5)),
        ("Workshop", "workshop", now - timedelta(days=25), now + timedelta(days=3)),
    ]
    categories = {}
    for name, slug, start, end in categories_data:
        cat, _ = ProposalCategory.objects.get_or_create(
            event=event,
            slug=slug,
            defaults={
                "name": name,
                "start_time": start,
                "end_time": end,
                "max_participants_limit": 24,
                "min_participants_limit": 2,
                "durations": ["PT1H", "PT2H", "PT3H"],
            },
        )
        categories[slug] = cat
    return categories


def _create_tag_categories(event: Event) -> dict[str, list[Tag]]:
    tags_by_category = {}
    for cat_name, icon, tag_names in TAG_CATEGORIES_DATA:
        tag_cat, _ = TagCategory.objects.get_or_create(
            name=cat_name, defaults={"icon": icon, "input_type": "select"}
        )
        # Link to all proposal categories
        for pc in ProposalCategory.objects.filter(event=event):
            pc.tag_categories.add(tag_cat)

        tags = []
        for tag_name in tag_names:
            tag, _ = Tag.objects.get_or_create(
                name=tag_name, category=tag_cat, defaults={"confirmed": True}
            )
            tags.append(tag)
        tags_by_category[cat_name] = tags
    return tags_by_category


def _create_personal_data_fields(
    event: Event, categories: dict[str, ProposalCategory]
) -> None:
    fields_data = [
        ("Discord Handle", "discord-handle", "text", None),
        (
            "Preferred Pronouns",
            "pronouns",
            "select",
            ["he/him", "she/her", "they/them"],
        ),
        ("T-shirt Size", "tshirt-size", "select", ["S", "M", "L", "XL", "XXL"]),
    ]
    for name, slug, field_type, options in fields_data:
        field, _ = PersonalDataField.objects.get_or_create(
            event=event, slug=slug, defaults={"name": name, "field_type": field_type}
        )
        if options:
            for i, opt in enumerate(options):
                PersonalDataFieldOption.objects.get_or_create(
                    field=field, value=opt, defaults={"label": opt, "order": i}
                )
        # Make required for RPG and Workshop categories
        for cat_slug in ("rpg", "workshop"):
            if cat_slug in categories:
                PersonalDataFieldRequirement.objects.get_or_create(
                    category=categories[cat_slug],
                    field=field,
                    defaults={"is_required": slug == "discord-handle"},
                )


def _create_session_fields(
    event: Event, categories: dict[str, ProposalCategory]
) -> None:
    fields_data = [
        ("RPG System", "rpg-system", "text", None),
        (
            "Player Experience",
            "player-experience",
            "select",
            ["Beginner", "Intermediate", "Advanced", "Any"],
        ),
        (
            "Materials Provided",
            "materials",
            "select",
            ["All included", "Bring your own", "Partial"],
        ),
    ]
    for name, slug, field_type, options in fields_data:
        field, _ = SessionField.objects.get_or_create(
            event=event, slug=slug, defaults={"name": name, "field_type": field_type}
        )
        if options:
            for i, opt in enumerate(options):
                SessionFieldOption.objects.get_or_create(
                    field=field, value=opt, defaults={"label": opt, "order": i}
                )
        # Add requirements to RPG category
        if "rpg" in categories:
            SessionFieldRequirement.objects.get_or_create(
                category=categories["rpg"],
                field=field,
                defaults={"is_required": slug == "rpg-system"},
            )


def _create_time_slots(event: Event) -> list[TimeSlot]:
    slots = []
    for hour_offset in (0, 2, 4, 6, 8):
        slot, _ = TimeSlot.objects.get_or_create(
            event=event,
            start_time=event.start_time + timedelta(hours=hour_offset),
            defaults={"end_time": event.start_time + timedelta(hours=hour_offset + 2)},
        )
        slots.append(slot)
    return slots


def _create_venue(event: Event) -> tuple[Venue, Space]:
    venue, _ = Venue.objects.get_or_create(
        event=event,
        slug="gaming-center",
        defaults={
            "name": "Central Gaming Center",
            "address": "ul. Planszowa 42, Kraków",
        },
    )
    area, _ = Area.objects.get_or_create(
        venue=venue,
        slug="main-hall",
        defaults={
            "name": "Main Hall",
            "description": "The big room with all the tables.",
        },
    )
    space, _ = Space.objects.get_or_create(
        area=area, slug="table-1", defaults={"name": "Table 1", "capacity": 8}
    )
    # Create a few more spaces
    for i in range(2, 6):
        Space.objects.get_or_create(
            area=area,
            slug=f"table-{i}",
            defaults={"name": f"Table {i}", "capacity": random.choice([4, 6, 8, 10])},
        )
    return venue, space


def _create_proposals(
    hosts: list,
    categories: dict[str, ProposalCategory],
    tags_by_category: dict[str, list[Tag]],
    time_slots: list[TimeSlot],
    sphere: Sphere,
    space: Space,
) -> None:
    genre_tags = tags_by_category.get("Genre", [])
    complexity_tags = tags_by_category.get("Complexity", [])
    language_tags = tags_by_category.get("Language", [])

    for i, row in enumerate(PROPOSALS):
        title, desc, host_idx, cat_slug, status, needs, reqs, min_age, plimit = row

        if Proposal.objects.filter(title=title).exists():
            continue

        category = categories[cat_slug]
        host = hosts[host_idx]

        session = None
        if status in {"unassigned", "scheduled"}:
            session = Session.objects.create(
                sphere=sphere,
                title=title,
                slug=f"session-{i}",
                description=desc,
                presenter_name=host.name,
                participants_limit=plimit,
                min_age=min_age,
            )
            if status == "scheduled":
                slot = time_slots[i % len(time_slots)]
                AgendaItem.objects.create(
                    session=session,
                    space=space,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    session_confirmed=True,
                )

        proposal = Proposal.objects.create(
            category=category,
            host=host,
            title=title,
            description=desc,
            needs=needs,
            requirements=reqs,
            min_age=min_age,
            participants_limit=plimit,
            rejected=(status == "rejected"),
            session=session,
        )

        # Add some random tags
        if genre_tags:
            proposal.tags.add(random.choice(genre_tags))
        if complexity_tags:
            proposal.tags.add(random.choice(complexity_tags))
        if language_tags:
            proposal.tags.add(random.choice(language_tags))

        # Add random time slot preferences
        chosen_slots = random.sample(
            time_slots, k=min(random.randint(1, 3), len(time_slots))
        )
        proposal.time_slots.set(chosen_slots)

    event = categories["rpg"].event
    count = Proposal.objects.filter(category__event=event).count()
    log.info("Created %d proposals", count)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log.info("Bootstrapping proposals demo data...")

    _site, sphere = _get_or_create_sphere()
    manager = _create_manager(sphere)
    hosts = _create_hosts()
    event = _create_event(sphere)
    categories = _create_categories(event)
    tags_by_category = _create_tag_categories(event)
    _create_personal_data_fields(event, categories)
    _create_session_fields(event, categories)
    time_slots = _create_time_slots(event)
    _venue, space = _create_venue(event)
    _create_proposals(hosts, categories, tags_by_category, time_slots, sphere, space)

    qs = Proposal.objects.filter(category__event=event)
    pending = qs.filter(rejected=False, session__isnull=True).count()
    rejected = qs.filter(rejected=True).count()
    accepted = qs.filter(rejected=False, session__isnull=False).count()
    cat_names = ", ".join(c.name for c in categories.values())

    log.info("")
    log.info("Done! Summary:")
    log.info("  Event: %s (slug: %s)", event.name, event.slug)
    log.info("  Categories: %s", cat_names)
    log.info("  Proposals: %d", qs.count())
    log.info("    Pending:  %d", pending)
    log.info("    Rejected: %d", rejected)
    log.info("    Accepted: %d", accepted)
    log.info("")
    log.info("  Login as: %s / admin123", manager.username)
    log.info("  Panel URL: /panel/event/%s/proposals/", event.slug)


if __name__ == "__main__":
    main()
