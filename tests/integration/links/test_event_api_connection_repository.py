"""Tests for `EventAPIConnectionRepository`."""

from datetime import UTC, datetime, timedelta

import pytest

from ludamus.adapters.db.django.models import Credential, Event, EventAPIConnection
from ludamus.links.db.django.repositories import EventAPIConnectionRepository
from ludamus.pacts import NotFoundError
from ludamus.pacts.multiverse import CheckResult, ConnectionCheckStatus


def _credential(sphere):
    return Credential.objects.create(
        sphere=sphere, display_name="Ticket API", credentials=b"opaque"
    )


def _other_event(other_sphere):
    now = datetime.now(UTC)
    return Event.objects.create(
        sphere=other_sphere,
        name="Other event",
        slug="other-event",
        start_time=now,
        end_time=now + timedelta(days=1),
    )


def _write_dict(credential):
    return {
        "credential_id": credential.pk,
        "class_name": "GenericTicketAPIClient",
        "config": {"url": "https://x.test/check", "count_json_path": "count"},
    }


def _make_row(event, credential, url="https://a.test/", path="n"):
    return EventAPIConnection.objects.create(
        event=event,
        credential=credential,
        class_name="GenericTicketAPIClient",
        config={"url": url, "count_json_path": path},
    )


class TestList:
    def test_lists_event_scoped_rows(self, event, sphere, non_root_sphere):
        credential = _credential(sphere)
        other_event = _other_event(non_root_sphere)
        _make_row(event, credential)
        _make_row(other_event, credential, url="https://b.test/")

        rows = EventAPIConnectionRepository.list_for_event(event.pk)

        assert [r.event_id for r in rows] == [event.pk]


class TestGet:
    def test_returns_dto(self, event, sphere):
        row = _make_row(event, _credential(sphere))

        dto = EventAPIConnectionRepository.get(event.pk, row.pk)

        assert dto.pk == row.pk
        assert dto.class_name == "GenericTicketAPIClient"
        assert dto.config == {"url": "https://a.test/", "count_json_path": "n"}

    def test_raises_not_found_on_wrong_event_scope(
        self, event, sphere, non_root_sphere
    ):
        other_event = _other_event(non_root_sphere)
        row = _make_row(other_event, _credential(sphere))

        with pytest.raises(NotFoundError):
            EventAPIConnectionRepository.get(event.pk, row.pk)


class TestCreateUpdateDelete:
    def test_create_persists(self, event, sphere):
        credential = _credential(sphere)

        dto = EventAPIConnectionRepository.create(event.pk, _write_dict(credential))

        stored = EventAPIConnection.objects.get(pk=dto.pk)
        assert stored.credential_id == credential.pk
        assert stored.config == {
            "url": "https://x.test/check",
            "count_json_path": "count",
        }

    def test_update_overwrites(self, event, sphere):
        credential = _credential(sphere)
        dto = EventAPIConnectionRepository.create(event.pk, _write_dict(credential))

        updated = EventAPIConnectionRepository.update(
            event.pk,
            dto.pk,
            {
                "credential_id": credential.pk,
                "class_name": "GenericTicketAPIClient",
                "config": {"url": "https://y.test/", "count_json_path": "total"},
            },
        )

        assert updated.config == {"url": "https://y.test/", "count_json_path": "total"}

    def test_update_raises_not_found(self, event):
        with pytest.raises(NotFoundError):
            EventAPIConnectionRepository.update(
                event.pk, 999_999, {"credential_id": 1, "class_name": "x", "config": {}}
            )

    def test_delete_removes_row(self, event, sphere):
        dto = EventAPIConnectionRepository.create(
            event.pk, _write_dict(_credential(sphere))
        )

        EventAPIConnectionRepository.delete(event.pk, dto.pk)

        assert not EventAPIConnection.objects.filter(pk=dto.pk).exists()


class TestUpdateLastCheck:
    def test_records_status_and_timestamp(self, event, sphere):
        dto = EventAPIConnectionRepository.create(
            event.pk, _write_dict(_credential(sphere))
        )

        EventAPIConnectionRepository.update_last_check(
            event.pk,
            dto.pk,
            CheckResult(status=ConnectionCheckStatus.OK, detail="passed"),
        )

        stored = EventAPIConnection.objects.get(pk=dto.pk)
        assert stored.last_check_status == ConnectionCheckStatus.OK.value
        assert stored.last_check_detail == "passed"
        assert stored.last_check_at is not None

    def test_raises_not_found(self, event):
        with pytest.raises(NotFoundError):
            EventAPIConnectionRepository.update_last_check(
                event.pk,
                999_999,
                CheckResult(status=ConnectionCheckStatus.OK, detail=""),
            )
