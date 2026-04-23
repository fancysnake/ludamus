"""Timetable business logic for the agenda scheduling feature."""

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ludamus.pacts import (
    NotFoundError,
    ScheduleChangeAction,
    ScheduleChangeLogData,
    SessionStatus,
)
from ludamus.pacts.chronology import (
    TIMETABLE_ROOM_PAGE_SIZE,
    TIMETABLE_SLOT_MINUTES,
    ConflictDTO,
    ConflictSeverity,
    ConflictType,
    HeatmapCellDTO,
    HeatmapCellStatus,
    HeatmapDTO,
    HeatmapRowDTO,
    TimetableCellDTO,
    TimetableGridDTO,
    TimetableRowDTO,
    TrackProgressDTO,
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
        self,
        session_pk: int,
        space_pk: int,
        start_time: datetime,
        end_time: datetime,
        user_pk: int | None = None,
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
        event = self._uow.sessions.read_event(session_pk)
        log_data: ScheduleChangeLogData = {
            "event_id": event.pk,
            "session_id": session_pk,
            "user_id": user_pk,
            "action": ScheduleChangeAction.ASSIGN,
            "new_space_id": space_pk,
            "new_start_time": start_time,
            "new_end_time": end_time,
        }
        self._uow.schedule_change_logs.create(log_data)

    def unassign_session(self, session_pk: int, user_pk: int | None = None) -> None:
        if (agenda_item := self._uow.agenda_items.read_by_session(session_pk)) is None:
            raise NotFoundError
        event = self._uow.sessions.read_event(session_pk)
        self._uow.agenda_items.delete(agenda_item.pk)
        self._uow.sessions.update(session_pk, {"status": SessionStatus.ACCEPTED})
        log_data: ScheduleChangeLogData = {
            "event_id": event.pk,
            "session_id": session_pk,
            "user_id": user_pk,
            "action": ScheduleChangeAction.UNASSIGN,
            "old_space_id": agenda_item.space_id,
            "old_start_time": agenda_item.start_time,
            "old_end_time": agenda_item.end_time,
        }
        self._uow.schedule_change_logs.create(log_data)

    def revert_change(self, log_pk: int, user_pk: int | None = None) -> None:
        log = self._uow.schedule_change_logs.read(log_pk)
        if log.action == ScheduleChangeAction.ASSIGN:
            agenda_item = self._uow.agenda_items.read_by_session(log.session_id)
            if agenda_item is None:
                raise NotFoundError
            self._uow.agenda_items.delete(agenda_item.pk)
            self._uow.sessions.update(
                log.session_id, {"status": SessionStatus.ACCEPTED}
            )
        elif log.action == ScheduleChangeAction.UNASSIGN:
            if (
                log.old_space_id is None
                or log.old_start_time is None
                or log.old_end_time is None
            ):
                msg = "Cannot revert UNASSIGN: missing original placement data"
                raise ValueError(msg)
            session = self._uow.sessions.read(log.session_id)
            if session.status != SessionStatus.ACCEPTED:
                msg = f"Session {log.session_id} is not in ACCEPTED status"
                raise ValueError(msg)
            self._uow.agenda_items.create(
                {
                    "session_id": log.session_id,
                    "space_id": log.old_space_id,
                    "start_time": log.old_start_time,
                    "end_time": log.old_end_time,
                    "session_confirmed": False,
                }
            )
            self._uow.sessions.update(
                log.session_id, {"status": SessionStatus.SCHEDULED}
            )
        else:
            msg = f"Cannot revert action: {log.action}"
            raise ValueError(msg)
        event = self._uow.sessions.read_event(log.session_id)
        revert_log: ScheduleChangeLogData = {
            "event_id": event.pk,
            "session_id": log.session_id,
            "user_id": user_pk,
            "action": ScheduleChangeAction.REVERT,
        }
        self._uow.schedule_change_logs.create(revert_log)


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
                    all_conflicts.append(
                        self._add_track_attribution(conflict, track_pk)
                    )

        return all_conflicts

    def _add_track_attribution(
        self, conflict: ConflictDTO, current_track_pk: int | None
    ) -> ConflictDTO:
        if conflict.type != ConflictType.FACILITATOR_OVERLAP:
            return conflict
        other_tracks = self._uow.tracks.list_by_session(conflict.session_pk)
        if current_track_pk is not None:
            other_tracks = [t for t in other_tracks if t.pk != current_track_pk]
        if not other_tracks:
            return conflict
        track = other_tracks[0]
        return ConflictDTO(
            type=conflict.type,
            severity=conflict.severity,
            session_title=conflict.session_title,
            session_pk=conflict.session_pk,
            description=conflict.description,
            track_name=track.name,
            manager_names=self._uow.tracks.list_manager_names(track.pk),
        )


class TimetableOverviewService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    def build_heatmap(self, event_pk: int) -> HeatmapDTO:
        event = self._uow.events.read(event_pk)
        spaces = self._uow.spaces.list_by_event(event_pk)
        all_items = self._uow.agenda_items.list_by_event(event_pk)
        all_conflicts = ConflictDetectionService(self._uow).list_all_for_track(
            event_pk, track_pk=None
        )
        conflict_session_pks = {c.session_pk for c in all_conflicts}

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
                overlapping = next(
                    (
                        it
                        for it in space_items.get(space.pk, [])
                        if it.start_time <= slot_time < it.end_time
                    ),
                    None,
                )
                if overlapping is None:
                    status = HeatmapCellStatus.EMPTY
                elif overlapping.session_id in conflict_session_pks:
                    status = HeatmapCellStatus.CONFLICT
                else:
                    status = HeatmapCellStatus.SCHEDULED
                cells.append(HeatmapCellDTO(space_pk=space.pk, status=status))
            rows.append(HeatmapRowDTO(time=slot_time, cells=cells))

        return HeatmapDTO(spaces=spaces, rows=rows)

    def all_conflicts_grouped(self, event_pk: int) -> dict[str, list[ConflictDTO]]:
        conflicts = ConflictDetectionService(self._uow).list_all_for_track(
            event_pk, track_pk=None
        )
        grouped: dict[str, list[ConflictDTO]] = {}
        for conflict in conflicts:
            if (key := conflict.type) not in grouped:
                grouped[key] = []
            grouped[key].append(conflict)
        return grouped

    def track_progress(self, event_pk: int) -> list[TrackProgressDTO]:
        tracks = self._uow.tracks.list_by_event(event_pk)
        result = []
        for track in tracks:
            sessions = self._uow.sessions.list_sessions_by_event(
                event_pk, track_pk=track.pk
            )
            accepted = [
                s
                for s in sessions
                if s.status in {SessionStatus.ACCEPTED, SessionStatus.SCHEDULED}
            ]
            scheduled = [s for s in sessions if s.status == SessionStatus.SCHEDULED]
            accepted_count = len(accepted)
            scheduled_count = len(scheduled)
            progress_pct = (
                round(scheduled_count * 100 / accepted_count) if accepted_count else 0
            )
            manager_names = self._uow.tracks.list_manager_names(track.pk)
            result.append(
                TrackProgressDTO(
                    track_pk=track.pk,
                    track_name=track.name,
                    manager_names=manager_names,
                    accepted_count=accepted_count,
                    scheduled_count=scheduled_count,
                    progress_pct=progress_pct,
                )
            )
        return result
