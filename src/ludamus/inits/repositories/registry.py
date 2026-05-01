from functools import cached_property

from ludamus.inits.repositories.chronology import ChronologyRepositories


class Repositories:
    """Lazy nested repository registry.

    Internal to inits — never imported from gates. Mills services receive
    specific repo protocols extracted from this tree, not the tree itself.
    """

    @cached_property
    def chronology(self) -> ChronologyRepositories:
        return ChronologyRepositories()
