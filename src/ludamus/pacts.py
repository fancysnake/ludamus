from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Iterable
    from contextlib import AbstractContextManager


class NotFoundError(Exception):
    pass


class ProposalCategoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime | None
    max_participants_limit: int
    min_participants_limit: int
    name: str
    pk: int
    slug: str
    start_time: datetime | None


class ProposalDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    description: str
    host_id: int
    min_age: int
    needs: str
    participants_limit: int
    pk: int
    requirements: str
    session_id: int | None
    title: str


class AgendaItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime
    pk: int
    session_confirmed: bool
    start_time: datetime


class SessionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    description: str
    min_age: int
    modification_time: datetime
    participants_limit: int
    pk: int
    presenter_name: str
    requirements: str
    slug: str
    sphere_id: int
    title: str


class SpaceDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    modification_time: datetime
    name: str
    pk: int
    slug: str


class TimeSlotDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime
    pk: int
    start_time: datetime


class TagCategoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    icon: str
    input_type: str
    name: str
    pk: int


class TagDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    confirmed: bool
    name: str
    pk: int


class SessionData(TypedDict):
    description: str
    min_age: int
    participants_limit: int
    presenter_name: str
    requirements: str
    slug: str
    sphere_id: int
    title: str


class AgendaItemData(TypedDict):
    end_time: datetime
    session_confirmed: bool
    session_id: int
    space_id: int
    start_time: datetime


class RoleData(TypedDict, total=False):
    """Data for creating a role"""

    sphere_id: int
    name: str
    description: str
    is_system: bool


class EventData(TypedDict, total=False):
    """Data for creating/updating an event"""

    sphere_id: int
    name: str
    slug: str
    description: str
    start_time: datetime
    end_time: datetime
    publication_time: datetime | None
    proposal_start_time: datetime | None
    proposal_end_time: datetime | None


class UserPermissionData(TypedDict, total=False):
    """Data for creating a user permission"""

    user_id: int
    sphere_id: int
    action: Action
    resource_type: ResourceType
    resource_id: int
    granted_from_role_id: int | None
    granted_by_id: int | None


class UserType(StrEnum):
    ACTIVE = "active"
    CONNECTED = "connected"
    ANONYMOUS = "anonymous"


class Action(StrEnum):
    """Actions that can be performed on resources"""

    # Universal actions
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    # Resource-specific actions
    APPROVE = "approve"  # proposals
    REJECT = "reject"  # proposals
    SCHEDULE = "schedule"  # sessions
    PUBLISH = "publish"  # events
    MANAGE = "manage"  # general management
    MANAGE_PERMISSIONS = "manage_permissions"  # grant/revoke permissions

    # Wildcard - can do anything
    ALL = "*"


class ResourceType(StrEnum):
    """Types of resources that can have permissions"""

    SPHERE = "sphere"
    EVENT = "event"
    PROPOSAL = "proposal"
    CATEGORY = "category"
    SESSION = "session"
    SPACE = "space"
    VENUE = "venue"

    # Wildcard
    ALL = "*"


# Registry of which actions apply to which resources
ACTION_APPLICABLE_TO: dict[Action, list[ResourceType]] = {
    Action.READ: [ResourceType.ALL],
    Action.CREATE: [
        ResourceType.EVENT,
        ResourceType.PROPOSAL,
        ResourceType.CATEGORY,
        ResourceType.SESSION,
        ResourceType.SPACE,
    ],
    Action.UPDATE: [
        ResourceType.EVENT,
        ResourceType.PROPOSAL,
        ResourceType.CATEGORY,
        ResourceType.SESSION,
        ResourceType.SPACE,
        ResourceType.VENUE,
    ],
    Action.DELETE: [
        ResourceType.EVENT,
        ResourceType.PROPOSAL,
        ResourceType.CATEGORY,
        ResourceType.SESSION,
        ResourceType.SPACE,
    ],
    Action.APPROVE: [ResourceType.PROPOSAL],
    Action.REJECT: [ResourceType.PROPOSAL],
    Action.SCHEDULE: [ResourceType.SESSION, ResourceType.EVENT],
    Action.PUBLISH: [ResourceType.EVENT],
    Action.MANAGE: [ResourceType.ALL],
    Action.MANAGE_PERMISSIONS: [ResourceType.SPHERE],
    Action.ALL: [ResourceType.ALL],
}


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date_joined: datetime
    discord_username: str
    email: str
    full_name: str
    is_active: bool
    is_authenticated: bool
    is_staff: bool
    is_superuser: bool
    manager_id: int | None = None
    name: str
    pk: int
    slug: str
    user_type: UserType
    username: str


class SiteDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    domain: str
    name: str
    pk: int


class SphereDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    pk: int
    site_id: int


class EventDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
    end_time: datetime
    name: str
    pk: int
    proposal_end_time: datetime | None
    proposal_start_time: datetime | None
    publication_time: datetime | None
    slug: str
    start_time: datetime


class RoleDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    sphere_id: int
    name: str
    description: str
    is_system: bool


class RolePermissionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    role_id: int
    action: Action
    resource_type: ResourceType


class UserPermissionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    user_id: int
    sphere_id: int
    action: Action
    resource_type: ResourceType
    resource_id: int
    granted_from_role_id: int | None
    granted_by_id: int | None
    granted_at: datetime


class UserData(TypedDict, total=False):
    discord_username: str
    email: str
    is_active: bool
    name: str
    password: str
    slug: str
    user_type: UserType
    username: str


@dataclass
class RequestContext:
    current_site_id: int
    current_sphere_id: int
    root_site_id: int
    root_sphere_id: int
    current_user_slug: str | None = None
    current_user_id: int | None = None


@dataclass
class AuthenticatedRequestContext(RequestContext):
    current_user_slug: str
    current_user_id: int


class SphereRepositoryProtocol(Protocol):
    def read_by_domain(self, domain: str) -> SphereDTO: ...
    def read(self, pk: int) -> SphereDTO: ...
    def read_site(self, sphere_id: int) -> SiteDTO: ...
    def is_manager(self, sphere_id: int, user_slug: str) -> bool: ...


class UserRepositoryProtocol(Protocol):
    def create(self, user_data: UserData) -> None: ...
    def read(self, slug: str) -> UserDTO: ...
    def update(self, user_slug: str, user_data: UserData) -> None: ...
    @staticmethod
    def email_exists(email: str, exclude_slug: str | None = None) -> bool: ...


class ProposalRepositoryProtocol(Protocol):
    def read_event(self, proposal_id: int) -> EventDTO: ...
    def read_host(self, proposal_id: int) -> UserDTO: ...
    def read_spaces(self, proposal_id: int) -> list[SpaceDTO]: ...
    def read_tag_ids(self, proposal_id: int) -> list[int]: ...
    def read_time_slot(self, proposal_id: int, time_slot_id: int) -> TimeSlotDTO: ...
    def read_time_slots(self, proposal_id: int) -> list[TimeSlotDTO]: ...
    def read(self, pk: int) -> ProposalDTO: ...
    def update(self, proposal_dto: ProposalDTO) -> None: ...


class SessionRepositoryProtocol(Protocol):
    def create(self, session_data: SessionData, tag_ids: Iterable[int]) -> int: ...
    def read(self, pk: int) -> SessionDTO: ...


class AgendaItemRepositoryProtocol(Protocol):
    def create(self, agenda_item_data: AgendaItemData) -> None: ...


class ConnectedUserRepositoryProtocol(Protocol):
    def create(self, manager_slug: str, user_data: UserData) -> None: ...
    def read_all(self, manager_slug: str) -> list[UserDTO]: ...
    def read(self, manager_slug: str, user_slug: str) -> UserDTO: ...
    def delete(self, manager_slug: str, user_slug: str) -> None: ...
    def update(
        self, manager_slug: str, user_slug: str, user_data: UserData
    ) -> None: ...


class EventRepositoryProtocol(Protocol):
    def create(self, event_data: EventData) -> EventDTO: ...
    def read(self, event_id: int) -> EventDTO: ...
    def update(self, event_id: int, event_data: EventData) -> EventDTO: ...
    def list_by_sphere(self, sphere_id: int) -> list[EventDTO]: ...
    def delete(self, event_id: int) -> None: ...


class RoleRepositoryProtocol(Protocol):
    def create(self, role_data: RoleData) -> RoleDTO: ...
    def read(self, role_id: int) -> RoleDTO: ...
    def update(self, role_id: int, role_data: RoleData) -> RoleDTO: ...
    def list_by_sphere(self, sphere_id: int) -> list[RoleDTO]: ...
    def delete(self, role_id: int) -> None: ...
    def add_permission(
        self, role_id: int, action: Action, resource_type: ResourceType
    ) -> None: ...
    def remove_permission(
        self, role_id: int, action: Action, resource_type: ResourceType
    ) -> None: ...
    def get_permissions(self, role_id: int) -> list[RolePermissionDTO]: ...


class UserPermissionRepositoryProtocol(Protocol):
    def grant(self, permission_data: UserPermissionData) -> UserPermissionDTO: ...
    def revoke(self, permission_id: int) -> None: ...
    def has_permission(
        self,
        user_id: int,
        sphere_id: int,
        action: Action,
        resource_type: ResourceType,
        resource_id: int,
    ) -> bool: ...
    def list_user_permissions(
        self, user_id: int, sphere_id: int
    ) -> list[UserPermissionDTO]: ...
    def has_any_permission_in_sphere(self, user_id: int, sphere_id: int) -> bool: ...


class UnitOfWorkProtocol(Protocol):
    @staticmethod
    def atomic() -> AbstractContextManager[None]: ...
    @staticmethod
    def login_user(request: Any, user_slug: str) -> None: ...
    @property
    def active_users(self) -> UserRepositoryProtocol: ...
    @property
    def agenda_items(self) -> AgendaItemRepositoryProtocol: ...
    @property
    def anonymous_users(self) -> UserRepositoryProtocol: ...
    @property
    def connected_users(self) -> ConnectedUserRepositoryProtocol: ...
    @property
    def proposals(self) -> ProposalRepositoryProtocol: ...
    @property
    def sessions(self) -> SessionRepositoryProtocol: ...
    @property
    def spheres(self) -> SphereRepositoryProtocol: ...
    @property
    def roles(self) -> RoleRepositoryProtocol: ...
    @property
    def user_permissions(self) -> UserPermissionRepositoryProtocol: ...


class RootRequestProtocol(Protocol):
    uow: UnitOfWorkProtocol
    context: RequestContext
