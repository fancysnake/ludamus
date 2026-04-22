"""Timetable business logic for the agenda scheduling feature."""

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ludamus.pacts import NotFoundError, SessionStatus
from ludamus.pacts.chronology import (
    TIMETABLE_ROOM_PAGE_SIZE,
    TIMETABLE_SLOT_MINUTES,
    ConflictDTO,
    ConflictSeverity,
    ConflictType,
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

    def assign_session(
        self, session_pk: int, space_pk: int, start_time: datetime, end_time: datetime
    ) -> None:
        session = self._uow.sessions.read(session_pk)
        if session.status != SessionStatus.ACCEPTED:
            msg = f"Session {session_pk} is not in ACCEPTED status"
            raise ValueError(msg)
        self._uow.agenda_items.create(
            {
                "session_id": session_pk,
                "space_id": space_pk,
                "start_time": start_time,
                "end_time": end_time,
                "session_confirmed": False,
            }
        )
        self._uow.sessions.update(session_pk, {"status": SessionStatus.SCHEDULED})

    def unassign_session(self, session_pk: int) -> None:
        if (agenda_item := self._uow.agenda_items.read_by_session(session_pk)) is None:
            raise NotFoundError
        self._uow.agenda_items.delete(agenda_item.pk)
        self._uow.sessions.update(session_pk, {"status": SessionStatus.ACCEPTED})


class ConflictDetectionService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    def detect_for_assignment(
        self, session_pk: int, space_pk: int, start_time: datetime, end_time: datetime
    ) -> list[ConflictDTO]:
        conflicts: list[ConflictDTO] = []
        session = self._uow.sessions.read(session_pk)

        # Space overlap
        overlapping_in_space = self._uow.agenda_items.list_overlapping_in_space(
            space_pk, start_time, end_time, exclude_session_pk=session_pk
        )
        conflicts.extend(
            [
                ConflictDTO(
                    type=ConflictType.SPACE_OVERLAP,
                    severity=ConflictSeverity.ERROR,
                    session_title=item.session_title,
                    session_pk=item.session_id,
                    description=f"Sala zajęta przez: {item.session_title}",
                )
                for item in overlapping_in_space
            ]
        )

        # Capacity exceeded
        space = self._uow.spaces.read(space_pk)
        if space.capacity is not None and space.capacity < session.participants_limit:
            conflicts.append(
                ConflictDTO(
                    type=ConflictType.CAPACITY_EXCEEDED,
                    severity=ConflictSeverity.WARNING,
                    session_title=session.title,
                    session_pk=session_pk,
                    description=(
                        f"Sala mieści {space.capacity} os., "
                        f"sesja wymaga {session.participants_limit}"
                    ),
                )
            )

        # Facilitator overlap
        facilitators = self._uow.sessions.read_facilitators(session_pk)
        for facilitator in facilitators:
            overlapping_for_facilitator = (
                self._uow.agenda_items.list_overlapping_by_facilitator(
                    facilitator.pk, start_time, end_time, exclude_session_pk=session_pk
                )
            )
            conflicts.extend(
                [
                    ConflictDTO(
                        type=ConflictType.FACILITATOR_OVERLAP,
                        severity=ConflictSeverity.ERROR,
                        session_title=item.session_title,
                        session_pk=item.session_id,
                        description=(
                            f"{facilitator.display_name} prowadzi "
                            f"równocześnie: {item.session_title}"
                        ),
                    )
                    for item in overlapping_for_facilitator
                ]
            )

        return conflicts

    def list_all_for_track(
        self, event_pk: int, track_pk: int | None
    ) -> list[ConflictDTO]:
        scheduled = (
            self._uow.agenda_items.list_by_event(event_pk)
            if track_pk is None
            else self._uow.agenda_items.list_by_track(track_pk)
        )

        all_conflicts: list[ConflictDTO] = []
        seen: set[tuple[int, int]] = set()
        for item in scheduled:
            conflicts = self.detect_for_assignment(
                session_pk=item.session_id,
                space_pk=item.space_id,
                start_time=item.start_time,
                end_time=item.end_time,
            )
            for conflict in conflicts:
                key = (item.session_id, conflict.session_pk)
                reverse_key = (conflict.session_pk, item.session_id)
                if key not in seen and reverse_key not in seen:
                    seen.add(key)
                    all_conflicts.append(conflict)

        return all_conflicts
