from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from freezegun import freeze_time

from ludamus.adapters.web.django.entities import (
    EventInfo,
    ParticipationInfo,
    SessionData,
    TagCategoryData,
    TagWithCategory,
)
from ludamus.gates.web.django.entities import UserInfo
from ludamus.pacts import AgendaItemDTO, SessionDTO, SessionStatus, SpaceDTO, VenueDTO
from tests.integration.utils import assert_response

FROZEN_TIME = "2026-01-15 12:00:00"
FROZEN_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _expected_event_info() -> EventInfo:
    start = FROZEN_NOW + timedelta(days=7)
    end = start + timedelta(hours=6)
    return EventInfo(
        cover_image_url=staticfiles_storage.url("placeholder-images/01.jpg"),
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


def _make_presenter() -> UserInfo:
    return UserInfo(
        avatar_url=None,
        discord_username="",
        full_name="Alex Designer",
        name="Alex Designer",
        pk=1,
        slug="alex-designer",
        username="alex",
    )


def _make_tags() -> list[TagWithCategory]:
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
    return [
        TagWithCategory(
            category=category_themes, category_id=1, confirmed=True, name=name, pk=i
        )
        for i, name in enumerate(tag_names, start=1)
    ]


def _make_loc(creation: datetime) -> dict:
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


def _expected_session_data() -> SessionData:
    base_time = FROZEN_NOW + timedelta(days=7)
    start = base_time.replace(hour=14, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=2)
    creation = FROZEN_NOW - timedelta(days=30)
    presenter = _make_presenter()
    tags = _make_tags()
    participant_users = [
        UserInfo(
            avatar_url=None,
            discord_username="",
            full_name="Sam Player",
            name="Sam Player",
            pk=10,
            slug="sam-player",
            username="sam",
        ),
        UserInfo(
            avatar_url=None,
            discord_username="",
            full_name="Jordan Gamer",
            name="Jordan Gamer",
            pk=11,
            slug="jordan-gamer",
            username="jordan",
        ),
    ]
    session_participations = [
        ParticipationInfo(user=u, status="confirmed", creation_time=creation)
        for u in participant_users
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
        loc=_make_loc(creation),
    )


def _expected_session_data_ended() -> SessionData:
    base_time = FROZEN_NOW - timedelta(hours=2)
    start = base_time.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=2)
    creation = FROZEN_NOW - timedelta(days=30)
    presenter = _make_presenter()
    tags = _make_tags()[:3]
    ended_participants = [
        UserInfo(
            avatar_url=None,
            discord_username="",
            full_name="Sam Player",
            name="Sam Player",
            pk=10,
            slug="sam-player",
            username="sam",
        ),
        UserInfo(
            avatar_url=None,
            discord_username="",
            full_name="Jordan Gamer",
            name="Jordan Gamer",
            pk=11,
            slug="jordan-gamer",
            username="jordan",
        ),
        UserInfo(
            avatar_url=None,
            discord_username="",
            full_name="Casey Demo",
            name="Casey Demo",
            pk=12,
            slug="casey-demo",
            username="casey",
        ),
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
        presenter=presenter,
        session=SessionDTO(
            contact_email="alex@example.com",
            creation_time=creation,
            description="Ended session for design preview.",
            min_age=0,
            modification_time=creation,
            participants_limit=6,
            pk=2,
            display_name="Alex Designer",
            requirements="",
            slug="design-session-ended",
            title="Ended Session (Design Preview)",
            category_id=17,
            needs="Lots of space",
            presenter_id=18,
            status=SessionStatus.ACCEPTED,
        ),
        tags=tags,
        is_full=True,
        full_participant_info="6/6",
        effective_participants_limit=6,
        enrolled_count=6,
        session_participations=ended_participations,
        loc=_make_loc(creation),
    )


class TestDesignPageView:
    URL = reverse("web:design")

    @freeze_time(FROZEN_TIME)
    def test_ok(self, client):
        response = client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "view": ANY,
                "design_event": _expected_event_info(),
                "design_session_data": _expected_session_data(),
                "design_session_data_ended": _expected_session_data_ended(),
                "design_radio_options": [
                    ("a", "Radio A", True, "design-radio-a"),
                    ("b", "Radio B", False, "design-radio-b"),
                ],
            },
            template_name=["design.html"],
        )
