"""Timetable business logic for the agenda scheduling feature."""

import math
from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING

from ludamus.pacts.chronology import (
    TIMETABLE_ROOM_PAGE_SIZE,
    TIMETABLE_SLOT_MINUTES,
    TimetableCellDTO,
    TimetableGridDTO,
    TimetableRowDTO,
)

if TYPE_CHECKING:
    from ludamus.pacts import AgendaItemDTO, UnitOfWorkProtocol


class TimetableService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    def build_grid(
        self, event_pk: int, track_pk: int | None = None, space_page: int = 1
    ) -> TimetableGridDTO:
        event = self._uow.events.read(event_pk)

        all_spaces = self._uow.spaces.list_by_event(event_pk)
        if track_pk is not None:
            track_space_pks = set(self._uow.tracks.list_space_pks(track_pk))
            all_spaces = [s for s in all_spaces if s.pk in track_space_pks]

        total_spaces = len(all_spaces)
        total_pages = max(1, math.ceil(total_spaces / TIMETABLE_ROOM_PAGE_SIZE))
        space_page = max(1, min(space_page, total_pages))
        start = (space_page - 1) * TIMETABLE_ROOM_PAGE_SIZE
        spaces = all_spaces[start : start + TIMETABLE_ROOM_PAGE_SIZE]

        all_items = self._uow.agenda_items.list_by_event(event_pk)
        space_pk_set = {s.pk for s in spaces}
        space_items: dict[int, list[AgendaItemDTO]] = defaultdict(list)
        for item in all_items:
            if item.space_id in space_pk_set:
                space_items[item.space_id].append(item)

        slot_delta = timedelta(minutes=TIMETABLE_SLOT_MINUTES)
        total_seconds = (event.end_time - event.start_time).total_seconds()
        num_slots = int(total_seconds / (TIMETABLE_SLOT_MINUTES * 60))
        time_slots = [event.start_time + slot_delta * i for i in range(num_slots)]

        rows = []
        for slot_time in time_slots:
            cells = []
            for space in spaces:
                items_in_space = space_items.get(space.pk, [])
                overlapping = next(
                    (
                        it
                        for it in items_in_space
                        if it.start_time <= slot_time < it.end_time
                    ),
                    None,
                )
                if overlapping is None:
                    cells.append(TimetableCellDTO(space_pk=space.pk))
                elif overlapping.start_time == slot_time:
                    rowspan = max(
                        1,
                        round(
                            (
                                overlapping.end_time - overlapping.start_time
                            ).total_seconds()
                            / (TIMETABLE_SLOT_MINUTES * 60)
                        ),
                    )
                    cells.append(
                        TimetableCellDTO(
                            space_pk=space.pk, agenda_item=overlapping, rowspan=rowspan
                        )
                    )
                else:
                    cells.append(
                        TimetableCellDTO(space_pk=space.pk, is_continuation=True)
                    )
            rows.append(TimetableRowDTO(time=slot_time, cells=cells))

        return TimetableGridDTO(
            spaces=spaces,
            rows=rows,
            page=space_page,
            total_pages=total_pages,
            total_spaces=total_spaces,
        )
