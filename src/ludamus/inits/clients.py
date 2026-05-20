from functools import cached_property
from typing import TYPE_CHECKING

from ludamus.links.docs_api.google import GoogleDocsApi

if TYPE_CHECKING:
    from ludamus.pacts.multiverse import DocsApiProtocol


class Clients:
    """Lazy flat external-client registry.

    Internal to inits — never imported from gates. Mills services receive
    specific client protocols from this tree, not the tree itself. Same
    growing rule as `repositories.py`: flat until ~12 leaves, then bucket.
    """

    @cached_property
    def docs_api(self) -> DocsApiProtocol:
        return GoogleDocsApi()
