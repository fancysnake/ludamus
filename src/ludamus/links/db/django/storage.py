from collections import defaultdict
from dataclasses import dataclass, field

from ludamus.adapters.db.django.models import (
    AgendaItem,
    Event,
    Proposal,
    Session,
    Space,
    Sphere,
    Tag,
    TimeSlot,
    User,
)
from ludamus.pacts import UserType


@dataclass
class Storage:  # pylint: disable=too-many-instance-attributes
    agenda_items: dict[int, AgendaItem] = field(default_factory=dict)
    connected_users_by_user: dict[str, dict[str, User]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    events: dict[int, Event] = field(default_factory=dict)
    proposals: dict[int, Proposal] = field(default_factory=dict)
    sessions: dict[int, Session] = field(default_factory=dict)
    spaces_by_event: dict[int, dict[int, Space]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    sphere_managers: dict[int, dict[str, User]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    spheres: dict[int, Sphere] = field(default_factory=dict)
    tags_by_proposal: dict[int, dict[int, Tag]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    time_slots_by_event: dict[int, dict[int, TimeSlot]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    users: dict[UserType, dict[str, User]] = field(
        default_factory=lambda: defaultdict(dict)
    )
