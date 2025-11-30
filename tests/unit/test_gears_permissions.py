from unittest.mock import Mock

import pytest

from ludamus.gears import (
    AuthorizationService,
    PermissionCheckRegistry,
    RoleAssignmentService,
    get_sphere_id_for_resource,
)
from ludamus.pacts import (
    Action,
    AuthenticatedRequestContext,
    ResourceType,
    UserPermissionData,
)


class TestGetSphereIdForResource:

    def test_sphere_returns_resource_id(self):
        uow = Mock()
        sphere_id = 42
        assert (
            get_sphere_id_for_resource(uow, ResourceType.SPHERE, sphere_id) == sphere_id
        )
        uow.assert_not_called()

    def test_event_returns_event_pk(self):
        uow = Mock()
        event_id = 100
        event = Mock(pk=event_id)
        uow.proposals.read_event.return_value = event

        sphere_id = get_sphere_id_for_resource(uow, ResourceType.EVENT, 42)

        assert sphere_id == event_id
        uow.proposals.read_event.assert_called_once_with(42)

    def test_proposal_navigates_to_sphere(self):
        uow = Mock()
        proposal_id = 10
        proposal = Mock(pk=proposal_id)
        event = Mock(pk=20)
        sphere_id = 30
        sphere = Mock(pk=sphere_id)
        uow.proposals.read.return_value = proposal
        uow.proposals.read_event.return_value = event
        uow.spheres.read.return_value = sphere

        assert (
            get_sphere_id_for_resource(uow, ResourceType.PROPOSAL, proposal_id)
            == sphere_id
        )
        uow.proposals.read.assert_called_once_with(proposal_id)
        uow.proposals.read_event.assert_called_once_with(proposal_id)
        uow.spheres.read.assert_called_once_with(20)

    def test_session_reads_sphere_id(self):
        uow = Mock()
        sphere_id = 50
        session = Mock(sphere_id=sphere_id)
        uow.sessions.read.return_value = session

        assert get_sphere_id_for_resource(uow, ResourceType.SESSION, 42) == sphere_id
        uow.sessions.read.assert_called_once_with(42)

    def test_unknown_resource_type_raises_value_error(self):
        uow = Mock()
        with pytest.raises(ValueError, match="Unknown resource type"):
            get_sphere_id_for_resource(uow, "invalid_type", 42)  # type: ignore[arg-type]


class TestPermissionCheckRegistry:

    def test_register_decorator_adds_check(self):
        # Clear registry for this test
        PermissionCheckRegistry._registry.clear()

        @PermissionCheckRegistry.register(Action.READ, ResourceType.PROPOSAL)
        def test_check(uow, user_id, resource_type, resource_id):  # noqa: ARG001
            return True

        checks = PermissionCheckRegistry.get_checks(Action.READ, ResourceType.PROPOSAL)
        assert test_check in checks
        # Cleanup
        PermissionCheckRegistry._registry.clear()

    def test_get_checks_includes_wildcards(self):
        PermissionCheckRegistry._registry.clear()

        @PermissionCheckRegistry.register(Action.READ, ResourceType.PROPOSAL)
        def exact_check(uow, user_id, resource_type, resource_id):  # noqa: ARG001
            return True

        @PermissionCheckRegistry.register(Action.ALL, ResourceType.PROPOSAL)
        def wildcard_action(uow, user_id, resource_type, resource_id):  # noqa: ARG001
            return True

        @PermissionCheckRegistry.register(Action.READ, ResourceType.ALL)
        def wildcard_resource(uow, user_id, resource_type, resource_id):  # noqa: ARG001
            return True

        @PermissionCheckRegistry.register(Action.ALL, ResourceType.ALL)
        def double_wildcard(uow, user_id, resource_type, resource_id):  # noqa: ARG001
            return True

        checks = PermissionCheckRegistry.get_checks(Action.READ, ResourceType.PROPOSAL)

        assert exact_check in checks
        assert wildcard_action in checks
        assert wildcard_resource in checks
        assert double_wildcard in checks
        # Cleanup
        PermissionCheckRegistry._registry.clear()


class TestAuthorizationService:

    @pytest.fixture
    def context(self):
        return AuthenticatedRequestContext(
            current_user_id=1,
            current_user_slug="testuser",
            current_sphere_id=10,
            current_site_id=1,
            root_site_id=1,
            root_sphere_id=10,
        )

    @pytest.fixture
    def uow(self):
        return Mock()

    def test_can_returns_true_for_direct_permission(self, context, uow):
        uow.user_permissions.has_permission.return_value = True
        auth = AuthorizationService(context, uow)

        assert auth.can(Action.READ, ResourceType.PROPOSAL, 42) is True
        uow.user_permissions.has_permission.assert_called_once_with(
            1, 10, Action.READ, ResourceType.PROPOSAL, 42
        )

    def test_can_returns_true_for_sphere_manager(self, context, uow):
        uow.user_permissions.has_permission.return_value = False
        uow.spheres.is_manager.return_value = True
        auth = AuthorizationService(context, uow)

        assert auth.can(Action.READ, ResourceType.PROPOSAL, 42) is True
        uow.spheres.is_manager.assert_called_once_with(10, "testuser")

    def test_can_checks_derived_permissions(self, context, uow):
        PermissionCheckRegistry._registry.clear()

        @PermissionCheckRegistry.register(Action.READ, ResourceType.PROPOSAL)
        def derived_check(check_uow, user_id, resource_type, resource_id):
            return user_id == 1 and resource_id == 42

        uow.user_permissions.has_permission.return_value = False
        uow.spheres.is_manager.return_value = False
        auth = AuthorizationService(context, uow)

        assert auth.can(Action.READ, ResourceType.PROPOSAL, 42) is True
        # Cleanup
        PermissionCheckRegistry._registry.clear()

    def test_can_returns_false_when_no_permission(self, context, uow):
        uow.user_permissions.has_permission.return_value = False
        uow.spheres.is_manager.return_value = False
        PermissionCheckRegistry._registry.clear()

        auth = AuthorizationService(context, uow)

        assert auth.can(Action.READ, ResourceType.PROPOSAL, 42) is False

    def test_can_raises_for_invalid_action_resource_combination(self, context, uow):
        auth = AuthorizationService(context, uow)

        with pytest.raises(ValueError, match="not applicable"):
            # APPROVE is not applicable to SPHERE
            auth.can(Action.APPROVE, ResourceType.SPHERE, 42)

    def test_require_raises_permission_denied(self, context, uow):
        from django.core.exceptions import PermissionDenied

        uow.user_permissions.has_permission.return_value = False
        uow.spheres.is_manager.return_value = False
        PermissionCheckRegistry._registry.clear()

        auth = AuthorizationService(context, uow)

        with pytest.raises(PermissionDenied, match="testuser lacks permission"):
            auth.require(Action.READ, ResourceType.PROPOSAL, 42)

    def test_require_succeeds_when_permitted(self, context, uow):
        uow.user_permissions.has_permission.return_value = True
        auth = AuthorizationService(context, uow)

        # Should not raise
        auth.require(Action.READ, ResourceType.PROPOSAL, 42)

    def test_has_any_permission_in_sphere_for_manager(self, context, uow):
        uow.spheres.is_manager.return_value = True
        auth = AuthorizationService(context, uow)

        assert auth.has_any_permission_in_sphere() is True

    def test_has_any_permission_in_sphere_checks_permissions(self, context, uow):
        uow.spheres.is_manager.return_value = False
        uow.user_permissions.has_any_permission_in_sphere.return_value = True
        auth = AuthorizationService(context, uow)

        assert auth.has_any_permission_in_sphere() is True
        uow.user_permissions.has_any_permission_in_sphere.assert_called_once_with(1, 10)


class TestRoleAssignmentService:

    @pytest.fixture
    def context(self):
        return AuthenticatedRequestContext(
            current_user_id=1,
            current_user_slug="admin",
            current_sphere_id=10,
            current_site_id=1,
            root_site_id=1,
            root_sphere_id=10,
        )

    @pytest.fixture
    def uow(self):
        return Mock()

    def test_assign_role_requires_manage_permissions(self, context, uow):
        from django.core.exceptions import PermissionDenied

        uow.user_permissions.has_permission.return_value = False
        uow.spheres.is_manager.return_value = False
        PermissionCheckRegistry._registry.clear()

        service = RoleAssignmentService(context, uow)

        with pytest.raises(PermissionDenied):
            service.assign_role(
                user_id=2, role_id=5, resource_type=ResourceType.EVENT, resource_id=20
            )

    def test_assign_role_copies_permissions_from_role(self, context, uow):
        # Setup permissions
        uow.user_permissions.has_permission.return_value = True
        role_perm1 = Mock(action=Action.READ, resource_type=ResourceType.PROPOSAL)
        role_perm2 = Mock(action=Action.UPDATE, resource_type=ResourceType.PROPOSAL)
        uow.roles.get_permissions.return_value = [role_perm1, role_perm2]

        created_perm1 = Mock()
        created_perm2 = Mock()
        uow.user_permissions.grant.side_effect = [created_perm1, created_perm2]

        service = RoleAssignmentService(context, uow)
        result = service.assign_role(
            user_id=2, role_id=5, resource_type=ResourceType.EVENT, resource_id=20
        )

        # Verify role permissions were fetched
        uow.roles.get_permissions.assert_called_once_with(5)

        # Verify grant was called twice with correct data
        assert uow.user_permissions.grant.call_count == 2

        call1 = uow.user_permissions.grant.call_args_list[0][0][0]
        assert call1 == UserPermissionData(
            user_id=2,
            sphere_id=10,
            action=Action.READ,
            resource_type=ResourceType.EVENT,
            resource_id=20,
            granted_from_role_id=5,
            granted_by_id=1,
        )

        call2 = uow.user_permissions.grant.call_args_list[1][0][0]
        assert call2 == UserPermissionData(
            user_id=2,
            sphere_id=10,
            action=Action.UPDATE,
            resource_type=ResourceType.EVENT,
            resource_id=20,
            granted_from_role_id=5,
            granted_by_id=1,
        )

        # Verify return value
        assert result == [created_perm1, created_perm2]
