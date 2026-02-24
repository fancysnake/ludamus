from unittest.mock import MagicMock

import pytest

from ludamus.adapters.web.django.entities import SessionData


def _make_session_data(
    effective_participants_limit: int = 10, enrolled_count: int = 0, **overrides
) -> SessionData:
    defaults = {
        "agenda_item": MagicMock(),
        "is_enrollment_available": True,
        "proposal": None,
        "presenter": MagicMock(),
        "session": MagicMock(),
        "tags": [],
        "is_full": enrolled_count >= effective_participants_limit,
        "full_participant_info": "",
        "effective_participants_limit": effective_participants_limit,
        "enrolled_count": enrolled_count,
        "session_participations": [],
        "loc": MagicMock(),
    }
    return SessionData(**(defaults | overrides))


class TestSessionDataSpotsLeft:
    def test_no_enrollments(self):
        data = _make_session_data(effective_participants_limit=10, enrolled_count=0)

        assert data.spots_left == data.effective_participants_limit

    def test_some_enrollments(self):
        data = _make_session_data(effective_participants_limit=10, enrolled_count=3)

        assert (
            data.spots_left == data.effective_participants_limit - data.enrolled_count
        )

    def test_full(self):
        data = _make_session_data(effective_participants_limit=10, enrolled_count=10)

        assert data.spots_left == 0

    def test_over_limit_clamps_to_zero(self):
        data = _make_session_data(effective_participants_limit=5, enrolled_count=7)

        assert data.spots_left == 0


class TestSessionDataSpotsScarce:
    @pytest.mark.parametrize(
        ("limit", "enrolled", "expected"),
        (
            # 0/10 enrolled → 100% left → not scarce
            (10, 0, False),
            # 5/10 enrolled → 50% left → not scarce
            (10, 5, False),
            # 7/10 enrolled → 30% left → not scarce
            (10, 7, False),
            # 8/10 enrolled → 20% left → not scarce (boundary: exactly 20%)
            (10, 8, False),
            # 9/10 enrolled → 10% left → scarce
            (10, 9, True),
            # 10/10 enrolled → 0% left → scarce
            (10, 10, True),
            # 4/5 enrolled → 20% left → not scarce (boundary)
            (5, 4, False),
            # 5/5 enrolled → 0% left → scarce
            (5, 5, True),
            # 1/1 enrolled → 0% left → scarce
            (1, 1, True),
            # 0/1 enrolled → 100% left → not scarce
            (1, 0, False),
        ),
    )
    def test_threshold(self, limit, enrolled, expected):
        data = _make_session_data(
            effective_participants_limit=limit, enrolled_count=enrolled
        )

        assert data.spots_scarce is expected

    def test_zero_limit_is_not_scarce(self):
        data = _make_session_data(effective_participants_limit=0, enrolled_count=0)

        assert data.spots_scarce is False


class TestSessionDataWaitingCount:
    def test_default_is_zero(self):
        data = _make_session_data()

        assert data.waiting_count == 0

    def test_explicit_value(self):
        waiting = 3
        data = _make_session_data(waiting_count=waiting)

        assert data.waiting_count == waiting
