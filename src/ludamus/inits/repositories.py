from functools import cached_property

from ludamus.links.db.django import repositories


class Repositories:
    """Lazy flat repository registry.

    Internal to inits — never imported from gates. Mills services receive
    specific repo protocols from this tree, not the tree itself. Buckets
    will appear when the leaf count grows past ~12.
    """

    @cached_property
    def personal_data_fields(self) -> repositories.PersonalDataFieldRepository:
        return repositories.PersonalDataFieldRepository()

    @cached_property
    def proposal_categories(self) -> repositories.ProposalCategoryRepository:
        return repositories.ProposalCategoryRepository()
