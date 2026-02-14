from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from ludamus.mills import PanelService, is_proposal_active
from ludamus.pacts import (
    DiscountTierDTO,
    EventDTO,
    EventStatsData,
    PanelStatsDTO,
    ScheduledProposalData,
)


class TestPanelService:
    @pytest.fixture
    def mock_uow(self):
        return MagicMock()

    @pytest.fixture
    def panel_service(self, mock_uow):
        return PanelService(mock_uow)

    def test_delete_venue_returns_false_when_venue_has_sessions(
        self, panel_service, mock_uow
    ):
        venue_pk = 42
        mock_uow.venues.has_sessions.return_value = True

        result = panel_service.delete_venue(venue_pk)

        assert result is False
        mock_uow.venues.has_sessions.assert_called_once_with(venue_pk)
        mock_uow.venues.delete.assert_not_called()

    def test_delete_area_returns_false_when_area_has_sessions(
        self, panel_service, mock_uow
    ):
        area_pk = 42
        mock_uow.areas.has_sessions.return_value = True

        result = panel_service.delete_area(area_pk)

        assert result is False
        mock_uow.areas.has_sessions.assert_called_once_with(area_pk)
        mock_uow.areas.delete.assert_not_called()

    def test_delete_space_returns_false_when_space_has_sessions(
        self, panel_service, mock_uow
    ):
        space_pk = 42
        mock_uow.spaces.has_sessions.return_value = True

        result = panel_service.delete_space(space_pk)

        assert result is False
        mock_uow.spaces.has_sessions.assert_called_once_with(space_pk)
        mock_uow.spaces.delete.assert_not_called()

    def test_get_event_stats_calculates_total_sessions(self, panel_service, mock_uow):
        total_proposals = 15
        mock_uow.events.get_stats_data.return_value = EventStatsData(
            pending_proposals=5,
            scheduled_sessions=10,
            total_proposals=total_proposals,
            unique_host_ids={1, 2, 3},
            rooms_count=4,
        )

        result = panel_service.get_event_stats(event_id=1)

        assert result.total_sessions == total_proposals
        mock_uow.events.get_stats_data.assert_called_once_with(1)

    def test_get_event_stats_counts_unique_hosts(self, panel_service, mock_uow):
        hosts = {10, 20, 30, 40, 50}
        mock_uow.events.get_stats_data.return_value = EventStatsData(
            pending_proposals=0,
            scheduled_sessions=0,
            total_proposals=0,
            unique_host_ids=hosts,
            rooms_count=0,
        )

        result = panel_service.get_event_stats(event_id=42)

        assert result.hosts_count == len(hosts)

    def test_get_event_stats_returns_panel_stats_dto(self, panel_service, mock_uow):
        pending_proposals = 3
        scheduled_sessions = 7
        total_proposals = 10
        unique_host_ids = {1, 2}
        rooms_count = 5
        mock_uow.events.get_stats_data.return_value = EventStatsData(
            pending_proposals=pending_proposals,
            scheduled_sessions=scheduled_sessions,
            total_proposals=total_proposals,
            unique_host_ids=unique_host_ids,
            rooms_count=rooms_count,
        )

        result = panel_service.get_event_stats(event_id=1)

        assert isinstance(result, PanelStatsDTO)
        assert result.pending_proposals == pending_proposals
        assert result.scheduled_sessions == scheduled_sessions
        assert result.total_proposals == total_proposals
        assert result.rooms_count == rooms_count
        assert result.hosts_count == len(unique_host_ids)
        assert result.total_sessions == total_proposals

    def test_get_event_stats_with_empty_hosts(self, panel_service, mock_uow):
        mock_uow.events.get_stats_data.return_value = EventStatsData(
            pending_proposals=0,
            scheduled_sessions=0,
            total_proposals=0,
            unique_host_ids=set(),
            rooms_count=0,
        )

        result = panel_service.get_event_stats(event_id=1)

        assert result.hosts_count == 0
        assert result.total_sessions == 0


class TestIsProposalActive:
    @pytest.fixture
    def base_event_data(self):
        now = datetime.now(tz=UTC)
        return {
            "description": "Test event",
            "end_time": now + timedelta(days=7),
            "name": "Test Event",
            "pk": 1,
            "proposal_end_time": now + timedelta(days=1),
            "proposal_start_time": now - timedelta(days=1),
            "publication_time": now - timedelta(days=2),
            "slug": "test-event",
            "sphere_id": 1,
            "start_time": now + timedelta(days=5),
        }

    def test_returns_false_when_proposal_start_time_is_none(self, base_event_data):
        base_event_data["proposal_start_time"] = None
        event = EventDTO(**base_event_data)

        assert is_proposal_active(event) is False

    def test_returns_false_when_proposal_end_time_is_none(self, base_event_data):
        base_event_data["proposal_end_time"] = None
        event = EventDTO(**base_event_data)

        assert is_proposal_active(event) is False

    def test_returns_false_when_both_proposal_times_are_none(self, base_event_data):
        base_event_data["proposal_start_time"] = None
        base_event_data["proposal_end_time"] = None
        event = EventDTO(**base_event_data)

        assert is_proposal_active(event) is False

    def test_returns_true_when_current_time_within_proposal_window(
        self, base_event_data
    ):
        event = EventDTO(**base_event_data)

        assert is_proposal_active(event) is True

    def test_returns_false_when_current_time_before_proposal_window(
        self, base_event_data
    ):
        now = datetime.now(tz=UTC)
        base_event_data["proposal_start_time"] = now + timedelta(days=1)
        base_event_data["proposal_end_time"] = now + timedelta(days=2)
        event = EventDTO(**base_event_data)

        assert is_proposal_active(event) is False

    def test_returns_false_when_current_time_after_proposal_window(
        self, base_event_data
    ):
        now = datetime.now(tz=UTC)
        base_event_data["proposal_start_time"] = now - timedelta(days=2)
        base_event_data["proposal_end_time"] = now - timedelta(days=1)
        event = EventDTO(**base_event_data)

        assert is_proposal_active(event) is False


def _make_proposal(
    *,
    host_id: int = 1,
    host_name: str = "Alice",
    host_email: str = "alice@example.com",
    host_slug: str = "alice",
    category_name: str = "RPG",
    duration_minutes: int = 60,
) -> ScheduledProposalData:
    now = datetime.now(tz=UTC)
    return ScheduledProposalData(
        host_id=host_id,
        host_name=host_name,
        host_email=host_email,
        host_slug=host_slug,
        category_name=category_name,
        start_time=now,
        end_time=now + timedelta(minutes=duration_minutes),
    )


def _make_tier(
    *,
    pk: int = 1,
    name: str = "Gold",
    percentage: int = 50,
    threshold: int = 3,
    threshold_type: str = "hours",
) -> DiscountTierDTO:
    return DiscountTierDTO(
        pk=pk,
        event_id=1,
        name=name,
        percentage=percentage,
        threshold=threshold,
        threshold_type=threshold_type,
    )


class TestGetHostSummaries:
    @pytest.fixture
    def mock_uow(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_uow):
        return PanelService(mock_uow)

    def test_empty_proposals_returns_empty_list(self, service, mock_uow):
        mock_uow.hosts.list_scheduled_proposals.return_value = []
        mock_uow.discount_tiers.list_by_event.return_value = []

        result = service.get_host_summaries(event_id=1)

        assert result == []

    def test_groups_by_host(self, service, mock_uow):
        alice_proposals = 2
        mock_uow.hosts.list_scheduled_proposals.return_value = [
            _make_proposal(host_id=1, host_name="Alice", host_slug="alice"),
            _make_proposal(host_id=1, host_name="Alice", host_slug="alice"),
            _make_proposal(host_id=2, host_name="Bob", host_slug="bob"),
        ]
        mock_uow.discount_tiers.list_by_event.return_value = []

        result = service.get_host_summaries(event_id=1)

        expected_hosts = 2
        assert len(result) == expected_hosts
        alice = next(h for h in result if h.name == "Alice")
        bob = next(h for h in result if h.name == "Bob")
        assert alice.session_count == alice_proposals
        assert bob.session_count == 1

    def test_ceiling_on_fractional_hours(self, service, mock_uow):
        mock_uow.hosts.list_scheduled_proposals.return_value = [
            _make_proposal(duration_minutes=45),
            _make_proposal(duration_minutes=80),
            _make_proposal(duration_minutes=120),
        ]
        mock_uow.discount_tiers.list_by_event.return_value = []

        result = service.get_host_summaries(event_id=1)

        # 45min -> 1h, 80min -> 2h, 120min -> 2h => total 5h
        expected_total_hours = 5
        assert result[0].total_hours == expected_total_hours

    def test_matches_highest_qualifying_tier(self, service, mock_uow):
        mock_uow.hosts.list_scheduled_proposals.return_value = [
            _make_proposal(duration_minutes=60),
            _make_proposal(duration_minutes=60),
            _make_proposal(duration_minutes=60),
        ]
        gold_threshold = 5
        gold = _make_tier(pk=1, name="Gold", percentage=50, threshold=gold_threshold)
        silver = _make_tier(pk=2, name="Silver", percentage=30, threshold=3)
        bronze = _make_tier(pk=3, name="Bronze", percentage=10, threshold=1)
        mock_uow.discount_tiers.list_by_event.return_value = [gold, silver, bronze]

        result = service.get_host_summaries(event_id=1)

        # 3 hours, threshold_type=hours => Silver (threshold=3)
        assert result[0].matched_tier == silver

    def test_uses_agenda_items_count_when_threshold_type_is_agenda_items(
        self, service, mock_uow
    ):
        mock_uow.hosts.list_scheduled_proposals.return_value = [
            _make_proposal(duration_minutes=30),
            _make_proposal(duration_minutes=30),
        ]
        tier = _make_tier(threshold=2, threshold_type="agenda_items", percentage=20)
        mock_uow.discount_tiers.list_by_event.return_value = [tier]

        result = service.get_host_summaries(event_id=1)

        # 2 sessions >= threshold 2 => matches
        assert result[0].matched_tier == tier

    def test_no_tiers_matched_tier_is_none(self, service, mock_uow):
        mock_uow.hosts.list_scheduled_proposals.return_value = [_make_proposal()]
        mock_uow.discount_tiers.list_by_event.return_value = []

        result = service.get_host_summaries(event_id=1)

        assert result[0].matched_tier is None

    def test_sorts_by_session_count_desc_then_name(self, service, mock_uow):
        mock_uow.hosts.list_scheduled_proposals.return_value = [
            _make_proposal(
                host_id=1,
                host_name="Zara",
                host_slug="zara",
                host_email="zara@example.com",
            ),
            _make_proposal(
                host_id=2,
                host_name="Alice",
                host_slug="alice-2",
                host_email="alice2@example.com",
            ),
            _make_proposal(
                host_id=2,
                host_name="Alice",
                host_slug="alice-2",
                host_email="alice2@example.com",
            ),
            _make_proposal(
                host_id=3,
                host_name="Bob",
                host_slug="bob",
                host_email="bob@example.com",
            ),
            _make_proposal(
                host_id=3,
                host_name="Bob",
                host_slug="bob",
                host_email="bob@example.com",
            ),
        ]
        mock_uow.discount_tiers.list_by_event.return_value = []

        result = service.get_host_summaries(event_id=1)

        assert [h.name for h in result] == ["Alice", "Bob", "Zara"]
