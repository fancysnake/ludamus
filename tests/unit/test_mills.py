from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from ludamus.mills import PanelService, is_proposal_active
from ludamus.pacts import EventDTO, EventStatsData, PanelStatsDTO


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
