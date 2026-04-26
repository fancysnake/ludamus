from __future__ import annotations

from django.db.models import Q

from ludamus.adapters.db.django.models import ScheduleChangeLog
from ludamus.pacts import (
    NotFoundError,
    ScheduleChangeAction,
    ScheduleChangeLogData,
    ScheduleChangeLogDTO,
    ScheduleChangeLogRepositoryProtocol,
)

_SELECT_RELATED = ("session", "user", "old_space", "new_space")


def _to_dto(log: ScheduleChangeLog) -> ScheduleChangeLogDTO:
    return ScheduleChangeLogDTO(
        pk=log.pk,
        event_id=log.event_id,
        session_id=log.session_id,
        session_title=log.session.title,
        user_id=log.user_id,
        user_name=log.user.name if log.user else "",
        action=ScheduleChangeAction(log.action),
        old_space_id=log.old_space_id,
        old_space_name=log.old_space.name if log.old_space else None,
        new_space_id=log.new_space_id,
        new_space_name=log.new_space.name if log.new_space else None,
        old_start_time=log.old_start_time,
        old_end_time=log.old_end_time,
        new_start_time=log.new_start_time,
        new_end_time=log.new_end_time,
        creation_time=log.creation_time,
    )


class ScheduleChangeLogRepository(ScheduleChangeLogRepositoryProtocol):
    @staticmethod
    def create(data: ScheduleChangeLogData) -> None:
        ScheduleChangeLog.objects.create(**data)

    @staticmethod
    def read(pk: int) -> ScheduleChangeLogDTO:
        try:
            log = ScheduleChangeLog.objects.select_related(*_SELECT_RELATED).get(pk=pk)
        except ScheduleChangeLog.DoesNotExist as err:
            msg = f"ScheduleChangeLog {pk} not found"
            raise NotFoundError(msg) from err
        return _to_dto(log)

    @staticmethod
    def list_by_event(
        event_pk: int, *, space_pk: int | None = None
    ) -> list[ScheduleChangeLogDTO]:
        qs = ScheduleChangeLog.objects.filter(event_id=event_pk).select_related(
            *_SELECT_RELATED
        )
        if space_pk is not None:
            qs = qs.filter(Q(old_space_id=space_pk) | Q(new_space_id=space_pk))
        return [_to_dto(log) for log in qs]
