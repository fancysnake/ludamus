from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from ludamus.adapters.db.django.models import Sphere


class ProposalCategoryDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime | None
    max_participants_limit: int
    min_participants_limit: int
    name: str
    pk: int
    slug: str
    start_time: datetime | None


class TagCategoryDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    icon: str
    input_type: str
    name: str
    pk: int


class TagDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    confirmed: bool
    name: str
    pk: int


class UserDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    birth_date: datetime | None
    date_joined: datetime
    email: str
    is_active: bool
    is_staff: bool
    name: str
    slug: str
    user_type: str
    username: str


class SiteDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    domain: str
    name: str


class SphereDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    name: str


class RootDAOProtocol(Protocol):
    @property
    def current_site(self) -> SiteDTO: ...

    @property
    def current_sphere(self) -> SphereDTO: ...

    @property
    def root_site(self) -> SiteDTO: ...

    @property
    def allowed_domains(self) -> list[str]: ...

    @property
    def current_sphere_orm(self) -> Sphere:  # TODO: Remove
        ...


class RootDAORequestProtocol(Protocol):
    root_dao: RootDAOProtocol
