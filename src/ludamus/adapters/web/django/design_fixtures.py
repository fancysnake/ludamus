"""Mock data for the design system page."""

from datetime import UTC, datetime, timedelta

from django.contrib.staticfiles.storage import staticfiles_storage

from ludamus.gates.web.django.entities import UserInfo
from ludamus.pacts import (
    AgendaItemDTO,
    LocationData,
    SessionDTO,
    SessionStatus,
    SpaceDTO,
    VenueDTO,
)

from .entities import (
    EventInfo,
    ParticipationInfo,
    SessionData,
    TagCategoryData,
    TagWithCategory,
)

_DESIGN_PLACEHOLDER_IMAGE = "placeholder-images/01.jpg"


def _mock_user(full_name: str, pk: int, slug: str, username: str) -> UserInfo:
    return UserInfo(
        avatar_url=None,
        discord_username="",
        full_name=full_name,
        name=full_name,
        pk=pk,
        slug=slug,
        username=username,
    )


def _mock_venue_and_space(creation: datetime) -> LocationData:
    venue = VenueDTO(
        address="",
        creation_time=creation,
        modification_time=creation,
        name="Main Hall",
        order=0,
        pk=1,
        slug="main-hall",
    )
    space = SpaceDTO(
        area_id=None,
        capacity=None,
        creation_time=creation,
        modification_time=creation,
        name="Table 1",
        order=0,
        pk=1,
        slug="table-1",
    )
    return {"venue": venue, "area": None, "space": space}


def mock_event_info() -> EventInfo:
    start = datetime.now(UTC) + timedelta(days=7)
    end = start + timedelta(hours=6)
    return EventInfo(
        cover_image_url=staticfiles_storage.url(_DESIGN_PLACEHOLDER_IMAGE),
        description=(
            "Design system preview event. Use this to debug the "
            "event card in isolation."
        ),
        end_time=end,
        is_ended=False,
        is_live=False,
        is_proposal_active=True,
        is_published=True,
        name="Design Preview Event",
        session_count=12,
        start_time=start,
        slug="design-preview",
    )


def mock_session_data() -> SessionData:
    base_time = datetime.now(UTC) + timedelta(days=7)
    start = base_time.replace(hour=14, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=2)
    creation = datetime.now(UTC) - timedelta(days=30)
    category_themes = TagCategoryData(icon="", name="Themes", pk=1)
    tag_names = [
        "horror",
        "mystery",
        "18+",
        "one-shot",
        "PbtA",
        "cooperative",
        "extra tag for popover",
        "fantasy",
        "sci-fi",
        "comedy",
        "drama",
        "sandbox",
        "narrative",
        "GM-less",
        "2-4h",
        "beginner-friendly",
        "mature themes",
        "improvisation",
        "pre-generated",
        "homebrew",
    ]
    tags = [
        TagWithCategory(
            category=category_themes, category_id=1, confirmed=True, name=name, pk=i
        )
        for i, name in enumerate(tag_names, start=1)
    ]
    presenter = _mock_user("Alex Designer", pk=1, slug="alex-designer", username="alex")
    participants = [
        _mock_user("Sam Player", pk=10, slug="sam-player", username="sam"),
        _mock_user("Jordan Gamer", pk=11, slug="jordan-gamer", username="jordan"),
    ]
    session_participations = [
        ParticipationInfo(user=u, status="confirmed", creation_time=creation)
        for u in participants
    ]
    return SessionData(
        agenda_item=AgendaItemDTO(
            end_time=end, pk=1, session_confirmed=True, start_time=start
        ),
        is_enrollment_available=True,
        presenter=presenter,
        session=SessionDTO(
            contact_email="alex@example.com",
            creation_time=creation,
            description=(
                "A sample session for the design page. Host and tags are mock data."
            ),
            min_age=16,
            modification_time=creation,
            participants_limit=6,
            pk=1,
            display_name="Alex Designer",
            requirements="",
            slug="design-session",
            title="Design System Session Card",
            category_id=17,
            needs="Lots of space",
            presenter_id=18,
            status=SessionStatus.ACCEPTED,
        ),
        tags=tags,
        is_full=False,
        full_participant_info="4/6",
        effective_participants_limit=6,
        enrolled_count=2,
        session_participations=session_participations,
        loc=_mock_venue_and_space(creation),
    )


def mock_session_data_ended() -> SessionData:
    data = mock_session_data()
    base_time = datetime.now(UTC) - timedelta(hours=2)
    start = base_time.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=2)
    creation = datetime.now(UTC) - timedelta(days=30)
    ended_participants = [
        _mock_user("Sam Player", pk=10, slug="sam-player", username="sam"),
        _mock_user("Jordan Gamer", pk=11, slug="jordan-gamer", username="jordan"),
        _mock_user("Casey Demo", pk=12, slug="casey-demo", username="casey"),
    ]
    ended_participations = [
        ParticipationInfo(user=u, status="confirmed", creation_time=creation)
        for u in ended_participants
    ]
    return SessionData(
        agenda_item=AgendaItemDTO(
            end_time=end, pk=2, session_confirmed=True, start_time=start
        ),
        is_enrollment_available=False,
        presenter=data.presenter,
        session=SessionDTO(
            contact_email="alex@example.com",
            creation_time=creation,
            description="Ended session for design preview.",
            min_age=0,
            modification_time=creation,
            participants_limit=6,
            pk=2,
            display_name=data.presenter.full_name,
            requirements="",
            slug="design-session-ended",
            title="Ended Session (Design Preview)",
            category_id=17,
            needs="Lots of space",
            presenter_id=18,
            status=SessionStatus.ACCEPTED,
        ),
        tags=data.tags[:3],
        is_full=True,
        full_participant_info="6/6",
        effective_participants_limit=6,
        enrolled_count=6,
        session_participations=ended_participations,
        loc=_mock_venue_and_space(creation),
    )
