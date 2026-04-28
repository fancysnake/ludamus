"""SessionState: typed access to Pydantic state held in ``request.session``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from django.contrib.sessions.backends.base import SessionBase


class SessionState[S: BaseModel]:
    """Typed handle to a Pydantic model stored in ``request.session``.

    Construct once at module level (or per-request when keying needs URL
    data); the schema is the source of truth for every read and write.
    Misspelling a field is a type error, not a silent miss.

    Useful anywhere a view stashes structured state across requests:
    multi-step wizards, draft forms, transient UI flags, and so on.
    """

    def __init__(self, key: str, schema: type[S]) -> None:
        self._key = key
        self._schema = schema

    def read(self, session: SessionBase) -> S | None:
        if (raw := session.get(self._key)) is None:
            return None
        return self._schema.model_validate(raw)

    def write(self, session: SessionBase, state: S) -> None:
        session[self._key] = state.model_dump(mode="json")
        session.modified = True

    def clear(self, session: SessionBase) -> None:
        session.pop(self._key, None)
