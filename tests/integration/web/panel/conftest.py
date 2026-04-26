"""Fixtures shared across panel integration tests."""

from datetime import timedelta

import pytest

from ludamus.adapters.db.django.models import AgendaItem
from tests.integration.conftest import SessionFactory, SpaceFactory


@pytest.fixture(name="timetable_scale_data")
def timetable_scale_data_fixture(event, area, proposal_category, sphere):
    spaces = [SpaceFactory(area=area, capacity=50) for _ in range(5)]
    sessions = [
        SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="pending",
            participants_limit=20,
            min_age=0,
        )
        for _ in range(20)
    ]

    # Schedule 10 sessions across the spaces (non-overlapping)
    start = event.start_time
    for idx, session in enumerate(sessions[:10]):
        space = spaces[idx % len(spaces)]
        slot_start = start + timedelta(hours=idx)
        slot_end = slot_start + timedelta(hours=1)
        AgendaItem.objects.create(
            session=session,
            space=space,
            start_time=slot_start,
            end_time=slot_end,
            session_confirmed=False,
        )
        session.status = "scheduled"
        session.save()

    return {"event": event, "spaces": spaces, "sessions": sessions}
