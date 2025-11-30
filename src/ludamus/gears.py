from collections import defaultdict
from collections.abc import Callable
from secrets import token_urlsafe
from typing import TYPE_CHECKING, ClassVar

from django.core.exceptions import PermissionDenied

from ludamus.pacts import (
    ACTION_APPLICABLE_TO,
    Action,
    AgendaItemData,
    AuthenticatedRequestContext,
    ProposalDTO,
    ResourceType,
    SessionData,
    UnitOfWorkProtocol,
    UserData,
    UserDTO,
    UserPermissionData,
    UserPermissionDTO,
    UserRepositoryProtocol,
    UserType,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    PermissionCheckFunc = Callable[[UnitOfWorkProtocol, int, ResourceType, int], bool]


class AnonymousEnrollmentService:
    SLUG_TEMPLATE = "code_{code}"

    def __init__(self, user_repository: UserRepositoryProtocol) -> None:
        self._user_repository = user_repository

    def get_user_by_code(self, code: str) -> UserDTO:
        slug = self.SLUG_TEMPLATE.format(code=code)
        user = self._user_repository.read(slug)
        return UserDTO.model_validate(user)

    def build_user(self, code: str) -> UserData:
        return UserData(
            username=f"anon_{token_urlsafe(8).lower()}",
            slug=self.SLUG_TEMPLATE.format(code=code),
            user_type=UserType.ANONYMOUS,
            is_active=False,
        )


class AcceptProposalService:
    def __init__(
        self, uow: UnitOfWorkProtocol, context: AuthenticatedRequestContext
    ) -> None:
        self._uow = uow
        self._context = context

    def can_accept_proposals(self) -> bool:
        user = self._uow.active_users.read(self._context.current_user_slug)
        if user.is_superuser or user.is_staff:
            return True

        return self._uow.spheres.is_manager(
            self._context.current_sphere_id, self._context.current_user_slug
        )

    def accept_proposal(
        self,
        *,
        proposal: ProposalDTO,
        slugifier: Callable[[str], str],
        space_id: int,
        time_slot_id: int,
    ) -> None:
        host = self._uow.proposals.read_host(proposal.pk)
        proposal_repository = self._uow.proposals
        tag_ids = proposal_repository.read_tag_ids(proposal.pk)
        time_slot = self._uow.proposals.read_time_slot(proposal.pk, time_slot_id)

        with self._uow.atomic():
            session_id = self._uow.sessions.create(
                SessionData(
                    sphere_id=self._context.current_sphere_id,
                    presenter_name=host.name,
                    title=proposal.title,
                    description=proposal.description,
                    requirements=proposal.requirements,
                    participants_limit=proposal.participants_limit,
                    min_age=proposal.min_age,
                    slug=slugifier(proposal.title),
                ),
                tag_ids=tag_ids,
            )

            self._uow.agenda_items.create(
                AgendaItemData(
                    space_id=space_id,
                    session_id=session_id,
                    session_confirmed=True,
                    start_time=time_slot.start_time,
                    end_time=time_slot.end_time,
                )
            )

            proposal.session_id = session_id
            proposal_repository.update(proposal)


# =============================================================================
# PERMISSION SYSTEM
# =============================================================================


def get_sphere_id_for_resource(
    uow: UnitOfWorkProtocol, resource_type: ResourceType, resource_id: int
) -> int:
    if resource_type == ResourceType.SPHERE:
        return resource_id
    if resource_type == ResourceType.EVENT:
        event = uow.proposals.read_event(resource_id)
        return event.pk  # Events are top-level, return event_id as sphere_id
    if resource_type == ResourceType.PROPOSAL:
        proposal = uow.proposals.read(resource_id)
        # Proposals belong to events which belong to spheres
        event = uow.proposals.read_event(proposal.pk)
        sphere = uow.spheres.read(event.pk)
        return sphere.pk
    if resource_type == ResourceType.SESSION:
        # Sessions have sphere_id directly via Session.sphere FK
        session = uow.sessions.read(resource_id)
        return session.sphere_id
    # Add other resource types as needed
    msg = f"Unknown resource type: {resource_type}"
    raise ValueError(msg)


class PermissionCheckRegistry:
    """Registry for permission derivation logic with wildcard support"""

    _registry: ClassVar[dict[Action, dict[ResourceType, list[PermissionCheckFunc]]]] = (
        defaultdict(lambda: defaultdict(list))
    )

    @classmethod
    def register(
        cls, action: Action, resource_type: ResourceType
    ) -> Callable[[PermissionCheckFunc], PermissionCheckFunc]:

        def decorator(func: PermissionCheckFunc) -> PermissionCheckFunc:
            cls._registry[action][resource_type].append(func)
            return func

        return decorator

    @classmethod
    def get_checks(
        cls, action: Action, resource_type: ResourceType
    ) -> list[PermissionCheckFunc]:
        checks = []

        # Exact match
        checks.extend(cls._registry[action][resource_type])

        # Wildcard action: (ALL, resource_type)
        checks.extend(cls._registry[Action.ALL][resource_type])

        # Wildcard resource: (action, ALL)
        checks.extend(cls._registry[action][ResourceType.ALL])

        # Double wildcard: (ALL, ALL)
        checks.extend(cls._registry[Action.ALL][ResourceType.ALL])

        return checks


# =============================================================================
# WILDCARD PERMISSION CHECKS
# =============================================================================


@PermissionCheckRegistry.register(Action.READ, ResourceType.ALL)
def can_read_if_has_any_permission_in_sphere(
    uow: UnitOfWorkProtocol, user_id: int, resource_type: ResourceType, resource_id: int
) -> bool:
    sphere_id = get_sphere_id_for_resource(uow, resource_type, resource_id)
    return uow.user_permissions.has_any_permission_in_sphere(user_id, sphere_id)


# =============================================================================
# SPECIFIC PERMISSION DERIVATIONS
# =============================================================================


@PermissionCheckRegistry.register(Action.APPROVE, ResourceType.PROPOSAL)
@PermissionCheckRegistry.register(Action.REJECT, ResourceType.PROPOSAL)
def can_manage_proposal_via_category(
    _uow: UnitOfWorkProtocol,
    _user_id: int,
    _resource_type: ResourceType,
    _resource_id: int,
) -> bool:
    # FIXME: Need proposal.category_id and proper sphere resolution
    return False  # Placeholder


# =============================================================================
# AUTHORIZATION SERVICE
# =============================================================================


class AuthorizationService:

    def __init__(
        self, context: AuthenticatedRequestContext, uow: UnitOfWorkProtocol
    ) -> None:
        self._context = context
        self._uow = uow

    def can(
        self, action: Action, resource_type: ResourceType, resource_id: int
    ) -> bool:
        # Validate action applies to resource type
        if action != Action.ALL and resource_type != ResourceType.ALL:
            applicable = ACTION_APPLICABLE_TO.get(action, [])
            if ResourceType.ALL not in applicable and resource_type not in applicable:
                msg = f"Action {action} not applicable to {resource_type}"
                raise ValueError(msg)

        # 1. Check direct permission
        if self._uow.user_permissions.has_permission(
            self._context.current_user_id,
            self._context.current_sphere_id,
            action,
            resource_type,
            resource_id,
        ):
            return True

        # 2. Check sphere managers (bypass via is_manager)
        if self._uow.spheres.is_manager(
            self._context.current_sphere_id, self._context.current_user_slug
        ):
            return True

        # 3. Check derived permissions via registry
        checks = PermissionCheckRegistry.get_checks(action, resource_type)
        return any(
            check_func(
                self._uow, self._context.current_user_id, resource_type, resource_id
            )
            for check_func in checks
        )

    def require(
        self, action: Action, resource_type: ResourceType, resource_id: int
    ) -> None:
        if not self.can(action, resource_type, resource_id):
            msg = (
                f"User {self._context.current_user_slug} lacks permission: "
                f"{action} on {resource_type}#{resource_id}"
            )
            raise PermissionDenied(msg)

    def has_any_permission_in_sphere(self) -> bool:
        # Get user to check superuser/staff status
        user = self._uow.active_users.read(self._context.current_user_slug)

        # Superusers and staff always have access
        if user.is_superuser or user.is_staff:
            return True

        # Sphere managers always have access
        if self._uow.spheres.is_manager(
            self._context.current_sphere_id, self._context.current_user_slug
        ):
            return True

        # Check if user has any permission in sphere
        return self._uow.user_permissions.has_any_permission_in_sphere(
            self._context.current_user_id, self._context.current_sphere_id
        )


class RoleAssignmentService:
    """Service for assigning roles to users (copying permissions)"""

    def __init__(
        self, context: AuthenticatedRequestContext, uow: UnitOfWorkProtocol
    ) -> None:
        self._context = context
        self._uow = uow

    def assign_role(
        self, user_id: int, role_id: int, resource_type: ResourceType, resource_id: int
    ) -> list[UserPermissionDTO]:
        # Verify current user can manage permissions
        auth = AuthorizationService(self._context, self._uow)
        auth.require(
            Action.MANAGE_PERMISSIONS,
            ResourceType.SPHERE,
            self._context.current_sphere_id,
        )

        # Get role permissions
        role_perms = self._uow.roles.get_permissions(role_id)

        # Create user permissions
        created_perms = []
        for role_perm in role_perms:
            perm = self._uow.user_permissions.grant(
                UserPermissionData(
                    user_id=user_id,
                    sphere_id=self._context.current_sphere_id,
                    action=role_perm.action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    granted_from_role_id=role_id,
                    granted_by_id=self._context.current_user_id,
                )
            )
            created_perms.append(perm)

        return created_perms
