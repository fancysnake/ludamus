from datetime import UTC, datetime
from unittest.mock import MagicMock

from ludamus.links.db.django.repositories import (
    ConnectedUserRepository,
    ProposalRepository,
    SphereRepository,
)
from ludamus.links.db.django.storage import Storage
from ludamus.pacts import UserType

MOCK_ENTITY_ID = 100


class TestSphereRepositoryIsManager:
    """Test cache-hit behavior for is_manager method."""

    def test_returns_true_when_user_in_cached_managers(self):
        storage = Storage()
        sphere_id = 1
        user_slug = "manager-slug"

        mock_manager = MagicMock()
        mock_manager.slug = user_slug
        storage.sphere_managers[sphere_id][user_slug] = mock_manager

        repo = SphereRepository(storage)

        result = repo.is_manager(sphere_id, user_slug)

        assert result is True

    def test_returns_false_when_user_not_in_cached_managers(self):
        storage = Storage()
        sphere_id = 1
        user_slug = "manager-slug"
        other_user_slug = "other-user"

        mock_manager = MagicMock()
        mock_manager.slug = user_slug
        storage.sphere_managers[sphere_id][user_slug] = mock_manager

        repo = SphereRepository(storage)

        result = repo.is_manager(sphere_id, other_user_slug)

        assert result is False


class TestProposalRepositoryReadTimeSlots:
    """Test read_time_slots uses proposal's M2M relationship."""

    def test_returns_proposal_time_slots_via_m2m(self):
        storage = Storage()
        proposal_id = 1

        mock_time_slot = MagicMock()
        mock_time_slot.pk = 100
        mock_time_slot.start_time = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)
        mock_time_slot.end_time = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)

        mock_proposal = MagicMock()
        mock_proposal.time_slots.all.return_value = [mock_time_slot]
        storage.proposals[proposal_id] = mock_proposal

        repo = ProposalRepository(storage)

        result = repo.read_time_slots(proposal_id)

        mock_proposal.time_slots.all.assert_called_once()
        assert len(result) == 1
        assert result[0].pk == MOCK_ENTITY_ID


class TestProposalRepositoryReadTagIds:
    """Test cache-hit behavior for read_tag_ids method."""

    def test_returns_cached_tag_ids_without_db_query(self):
        storage = Storage()
        proposal_id = 1

        mock_proposal = MagicMock()
        storage.proposals[proposal_id] = mock_proposal

        mock_tag = MagicMock()
        mock_tag.id = 100
        mock_tag.pk = 100
        storage.tags_by_proposal[proposal_id][mock_tag.id] = mock_tag

        repo = ProposalRepository(storage)

        result = repo.read_tag_ids(proposal_id)

        mock_proposal.tags.all.assert_not_called()
        assert result == [100]


class TestConnectedUserRepositoryReadAll:
    """Test cache-hit behavior for read_all method."""

    def test_returns_cached_connected_users_without_db_query(self):
        storage = Storage()
        manager_slug = "manager-slug"

        mock_manager = MagicMock()
        mock_manager.slug = manager_slug
        mock_manager.pk = 1
        storage.users[UserType.ACTIVE][manager_slug] = mock_manager

        mock_connected_user = MagicMock()
        mock_connected_user.pk = 2
        mock_connected_user.slug = "connected-slug"
        mock_connected_user.username = "connected"
        mock_connected_user.email = "connected@example.com"
        mock_connected_user.name = "Connected User"
        mock_connected_user.full_name = "Connected User"
        mock_connected_user.discord_username = ""
        mock_connected_user.user_type = UserType.CONNECTED
        mock_connected_user.manager = mock_manager
        mock_connected_user.manager_id = 1
        mock_connected_user.date_joined = datetime(2025, 1, 1, tzinfo=UTC)
        mock_connected_user.is_active = True
        mock_connected_user.is_authenticated = True
        mock_connected_user.is_staff = False
        mock_connected_user.is_superuser = False
        storage.connected_users_by_user[manager_slug][
            mock_connected_user.slug
        ] = mock_connected_user

        repo = ConnectedUserRepository(storage)

        result = repo.read_all(manager_slug)

        mock_manager.connected.all.assert_not_called()
        assert len(result) == 1
        assert result[0].slug == "connected-slug"
