from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

from ludamus.gates.web.django.entities import UserInfo
from ludamus.pacts import EncounterRSVPDTO, NotFoundError, UnitOfWorkProtocol

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def build_attendee_list(
    rsvps: Sequence[EncounterRSVPDTO],
    uow: UnitOfWorkProtocol,
    gravatar_url: Callable[[str], str | None],
) -> list[UserInfo]:
    user_ids = [r.user_id for r in rsvps if r.user_id]
    user_map: dict[int, UserInfo] = {}
    for uid in user_ids:
        with suppress(NotFoundError):
            user_map[uid] = UserInfo.from_user_dto(
                uow.active_users.read_by_id(uid), gravatar_url=gravatar_url
            )

    attendees: list[UserInfo] = []
    for rsvp in rsvps:
        if rsvp.user_id and rsvp.user_id in user_map:
            attendees.append(user_map[rsvp.user_id])
        else:
            attendees.append(
                UserInfo(
                    avatar_url=None,
                    discord_username="",
                    full_name="",
                    name=rsvp.name or str(rsvp.user_id),
                    pk=0,
                    slug="",
                    username="",
                )
            )
    return attendees
