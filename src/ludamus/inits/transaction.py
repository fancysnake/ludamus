from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from contextlib import AbstractContextManager


class DjangoTransaction:
    @staticmethod
    def atomic() -> AbstractContextManager[None]:
        return transaction.atomic()
