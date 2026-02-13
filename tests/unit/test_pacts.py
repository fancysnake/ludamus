from datetime import datetime

from pydantic import BaseModel

from ludamus.pacts import ProposalListItemDTO, ProposalListResult


class TestProposalListItemDTO:
    def test_is_pydantic_base_model(self):
        assert issubclass(ProposalListItemDTO, BaseModel)

    def test_creation_time_annotation_is_datetime(self):
        hints = ProposalListItemDTO.__annotations__
        assert hints["creation_time"] is datetime


class TestProposalListResult:
    def test_is_pydantic_base_model(self):
        assert issubclass(ProposalListResult, BaseModel)
