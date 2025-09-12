from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class ProposalCategoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime | None
    max_participants_limit: int
    min_participants_limit: int
    name: str
    pk: int
    slug: str
    start_time: datetime | None


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


class UserDTO(BaseModel):
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


class SiteDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    domain: str
    name: str
    pk: int


class SphereDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    pk: int


class RootDAOProtocol(Protocol):
    @property
    def current_site(self) -> SiteDTO: ...

    @property
    def current_sphere(self) -> SphereDTO: ...

    @property
    def root_site(self) -> SiteDTO: ...

    @property
    def allowed_domains(self) -> list[str]: ...


class RootDAORequestProtocol(Protocol):
    root_dao: RootDAOProtocol
