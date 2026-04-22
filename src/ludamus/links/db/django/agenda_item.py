from ludamus.adapters.db.django.models import AgendaItem
from ludamus.pacts import (
    AgendaItemData,
    AgendaItemDTO,
    AgendaItemRepositoryProtocol,
    AgendaItemUpdateData,
    NotFoundError,
    SessionStatus,
)

_SELECT_RELATED = ("session", "session__category")


def _to_dto(item: AgendaItem) -> AgendaItemDTO:
    duration_minutes = int((item.end_time - item.start_time).total_seconds() / 60)
    return AgendaItemDTO(
        end_time=item.end_time,
        pk=item.pk,
        session_confirmed=item.session_confirmed,
        start_time=item.start_time,
        space_id=item.space_id,
        session_id=item.session_id,
        session_title=item.session.title,
        presenter_name=item.session.display_name,
        session_duration_minutes=duration_minutes,
        session_status=SessionStatus(item.session.status),
        category_name=(
            item.session.category.name if item.session.category is not None else None
        ),
    )


class AgendaItemRepository(AgendaItemRepositoryProtocol):
    @staticmethod
    def create(agenda_item_data: AgendaItemData) -> None:
        AgendaItem.objects.create(**agenda_item_data)

    @staticmethod
    def read(pk: int) -> AgendaItemDTO:
        try:
            item = AgendaItem.objects.select_related(*_SELECT_RELATED).get(pk=pk)
        except AgendaItem.DoesNotExist as err:
            raise NotFoundError from err
        return _to_dto(item)

    @staticmethod
    def list_by_event(event_pk: int) -> list[AgendaItemDTO]:
        items = AgendaItem.objects.filter(
            space__area__venue__event_id=event_pk
        ).select_related(*_SELECT_RELATED)
        return [_to_dto(item) for item in items]

    @staticmethod
    def list_by_space(space_pk: int) -> list[AgendaItemDTO]:
        items = AgendaItem.objects.filter(space_id=space_pk).select_related(
            *_SELECT_RELATED
        )
        return [_to_dto(item) for item in items]

    @staticmethod
    def list_by_track(track_pk: int) -> list[AgendaItemDTO]:
        items = AgendaItem.objects.filter(session__tracks__pk=track_pk).select_related(
            *_SELECT_RELATED
        )
        return [_to_dto(item) for item in items]

    @staticmethod
    def read_by_session(session_pk: int) -> AgendaItemDTO | None:
        try:
            item = AgendaItem.objects.select_related(*_SELECT_RELATED).get(
                session_id=session_pk
            )
        except AgendaItem.DoesNotExist:
            return None
        return _to_dto(item)

    @staticmethod
    def update(pk: int, data: AgendaItemUpdateData) -> None:
        AgendaItem.objects.filter(pk=pk).update(**data)

    @staticmethod
    def delete(pk: int) -> None:
        AgendaItem.objects.filter(pk=pk).delete()
