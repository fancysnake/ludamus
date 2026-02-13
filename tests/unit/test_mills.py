from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from ludamus.mills import PanelService, compute_proposal_status, is_proposal_active
from ludamus.pacts import (
    EventDTO,
    EventStatsData,
    PanelStatsDTO,
    ProposalActionError,
    ProposalDetailDTO,
    ProposalDTO,
    ProposalListItemDTO,
    ProposalListResult,
    ProposalStatus,
    TagDTO,
    TimeSlotDTO,
    UserDTO,
    UserType,
)

NOW = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)


def _make_proposal_dto(**overrides):
    defaults = {
        "pk": 1,
        "title": "Test Proposal",
        "description": "A test proposal",
        "host_id": 10,
        "min_age": 0,
        "needs": "",
        "participants_limit": 6,
        "rejected": False,
        "requirements": "",
        "session_id": None,
        "creation_time": NOW,
    }
    defaults.update(overrides)
    return ProposalDTO(**defaults)


def _make_user_dto(**overrides):
    defaults = {
        "pk": 10,
        "slug": "host-slug",
        "username": "hostuser",
        "email": "host@example.com",
        "name": "Host Name",
        "full_name": "Host Name",
        "discord_username": "",
        "user_type": UserType.ACTIVE,
        "manager_id": None,
        "date_joined": NOW,
        "is_active": True,
        "is_authenticated": True,
        "is_staff": False,
        "is_superuser": False,
    }
    defaults.update(overrides)
    return UserDTO(**defaults)


def _make_list_item(**overrides):
    defaults = {
        "pk": 1,
        "title": "Test",
        "description": "Desc",
        "host_name": "Host",
        "host_id": 10,
        "category_name": "Cat",
        "category_id": 1,
        "status": ProposalStatus.PENDING.value,
        "creation_time": NOW,
        "session_id": None,
    }
    defaults.update(overrides)
    return ProposalListItemDTO(**defaults)


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


class TestComputeProposalStatus:
    def test_pending_when_not_rejected_and_no_session(self):
        result = compute_proposal_status(
            rejected=False, session_id=None, has_agenda_item=False
        )

        assert result == ProposalStatus.PENDING.value

    def test_rejected_when_rejected_is_true(self):
        result = compute_proposal_status(
            rejected=True, session_id=None, has_agenda_item=False
        )

        assert result == ProposalStatus.REJECTED.value

    def test_scheduled_when_session_and_agenda_item(self):
        result = compute_proposal_status(
            rejected=False, session_id=5, has_agenda_item=True
        )

        assert result == ProposalStatus.SCHEDULED.value

    def test_unassigned_when_session_but_no_agenda_item(self):
        result = compute_proposal_status(
            rejected=False, session_id=5, has_agenda_item=False
        )

        assert result == ProposalStatus.UNASSIGNED.value


class TestPanelServiceRejectProposal:
    @pytest.fixture
    def mock_uow(self):
        return MagicMock()

    def test_calls_repo_with_event_scope(self, mock_uow):
        mock_uow.proposals.read_for_event.return_value = _make_proposal_dto(
            rejected=False, session_id=None
        )
        mock_uow.proposals.has_agenda_item.return_value = False
        service = PanelService(mock_uow)

        service.reject_proposal(event_id=10, proposal_id=1)

        mock_uow.proposals.read_for_event.assert_called_once_with(10, 1)
        mock_uow.proposals.reject.assert_called_once_with(1)

    def test_fails_when_already_rejected(self, mock_uow):
        mock_uow.proposals.read_for_event.return_value = _make_proposal_dto(
            rejected=True
        )
        service = PanelService(mock_uow)

        with pytest.raises(ProposalActionError):
            service.reject_proposal(event_id=10, proposal_id=1)

        mock_uow.proposals.reject.assert_not_called()

    def test_fails_when_scheduled(self, mock_uow):
        mock_uow.proposals.read_for_event.return_value = _make_proposal_dto(
            rejected=False, session_id=5
        )
        mock_uow.proposals.has_agenda_item.return_value = True
        service = PanelService(mock_uow)

        with pytest.raises(ProposalActionError):
            service.reject_proposal(event_id=10, proposal_id=1)

        mock_uow.proposals.reject.assert_not_called()


class TestPanelServiceUnrejectProposal:
    @pytest.fixture
    def mock_uow(self):
        return MagicMock()

    def test_unrejects_rejected_proposal(self, mock_uow):
        mock_uow.proposals.read_for_event.return_value = _make_proposal_dto(
            rejected=True
        )
        service = PanelService(mock_uow)

        service.unreject_proposal(event_id=10, proposal_id=1)

        mock_uow.proposals.read_for_event.assert_called_once_with(10, 1)
        mock_uow.proposals.unreject.assert_called_once_with(1)

    def test_fails_when_not_rejected(self, mock_uow):
        mock_uow.proposals.read_for_event.return_value = _make_proposal_dto(
            rejected=False
        )
        service = PanelService(mock_uow)

        with pytest.raises(ProposalActionError):
            service.unreject_proposal(event_id=10, proposal_id=1)

        mock_uow.proposals.unreject.assert_not_called()


class TestPanelServiceGetProposalDetail:
    @pytest.fixture
    def mock_uow(self):
        return MagicMock()

    def test_returns_aggregated_data(self, mock_uow):
        proposal = _make_proposal_dto(rejected=False, session_id=None)
        host = _make_user_dto()
        tags = [TagDTO(pk=1, name="RPG", category_id=1, confirmed=True)]
        time_slots = [TimeSlotDTO(pk=1, start_time=NOW, end_time=NOW)]

        mock_uow.proposals.read_for_event.return_value = proposal
        mock_uow.proposals.read_host.return_value = host
        mock_uow.proposals.read_tags.return_value = tags
        mock_uow.proposals.read_time_slots.return_value = time_slots
        mock_uow.proposals.has_agenda_item.return_value = False
        service = PanelService(mock_uow)

        result = service.get_proposal_detail(event_id=10, proposal_id=1)

        assert isinstance(result, ProposalDetailDTO)
        assert result.proposal == proposal
        assert result.host == host
        assert result.tags == tags
        assert result.time_slots == time_slots
        assert result.status == ProposalStatus.PENDING.value


class TestPanelServiceListProposals:
    @pytest.fixture
    def mock_uow(self):
        return MagicMock()

    def test_computes_statuses_and_filters(self, mock_uow):
        items = [
            _make_list_item(pk=1, status=ProposalStatus.PENDING.value),
            _make_list_item(pk=2, status=ProposalStatus.REJECTED.value),
            _make_list_item(pk=3, status=ProposalStatus.PENDING.value),
        ]
        total_items = len(items)
        expected_pending = 2
        mock_uow.proposals.list_by_event.return_value = ProposalListResult(
            proposals=items,
            status_counts={},
            total_count=total_items,
            filtered_count=total_items,
        )
        service = PanelService(mock_uow)

        result = service.list_proposals(
            event_id=10, filters={"statuses": ["PENDING"], "page": 1, "page_size": 10}
        )

        assert result.total_count == total_items
        assert result.filtered_count == expected_pending
        assert len(result.proposals) == expected_pending
        assert all(p.status == "PENDING" for p in result.proposals)

    def test_status_counts_unaffected_by_status_filter(self, mock_uow):
        items = [
            _make_list_item(pk=1, status=ProposalStatus.PENDING.value),
            _make_list_item(pk=2, status=ProposalStatus.REJECTED.value),
            _make_list_item(pk=3, status=ProposalStatus.SCHEDULED.value),
        ]
        total_items = len(items)
        mock_uow.proposals.list_by_event.return_value = ProposalListResult(
            proposals=items,
            status_counts={},
            total_count=total_items,
            filtered_count=total_items,
        )
        service = PanelService(mock_uow)

        result = service.list_proposals(
            event_id=10, filters={"statuses": ["PENDING"], "page": 1, "page_size": 10}
        )

        assert result.status_counts["PENDING"] == 1
        assert result.status_counts["REJECTED"] == 1
        assert result.status_counts["SCHEDULED"] == 1
        assert result.status_counts["UNASSIGNED"] == 0
