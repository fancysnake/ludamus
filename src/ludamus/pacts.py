from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
