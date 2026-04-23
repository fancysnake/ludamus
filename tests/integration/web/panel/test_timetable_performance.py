"""Performance tests for timetable views — bounded query counts at scale."""

from http import HTTPStatus

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

_GRID_QUERY_LIMIT = 30
_CONFLICT_QUERY_LIMIT = 100
_OVERVIEW_QUERY_LIMIT = 100


class TestTimetableQueryBounds:
    def test_timetable_grid_bounded_queries(
        self, authenticated_client, active_user, sphere, timetable_scale_data
    ):
        """Timetable grid partial should use a bounded number of DB queries."""
        event = timetable_scale_data["event"]
        sphere.managers.add(active_user)

        url = reverse("panel:timetable-grid-part", kwargs={"slug": event.slug})
        with CaptureQueriesContext(connection) as ctx:
            response = authenticated_client.get(url)

        assert response.status_code == HTTPStatus.OK
        count = len(ctx.captured_queries)
        assert (
            count <= _GRID_QUERY_LIMIT
        ), f"Grid used {count} queries, expected ≤ {_GRID_QUERY_LIMIT}"

    def test_conflict_detection_bounded_queries(
        self, authenticated_client, active_user, sphere, timetable_scale_data
    ):
        """Conflict panel should use a bounded number of DB queries."""
        event = timetable_scale_data["event"]
        sphere.managers.add(active_user)

        url = reverse("panel:timetable-conflicts-part", kwargs={"slug": event.slug})
        with CaptureQueriesContext(connection) as ctx:
            response = authenticated_client.get(url)

        assert response.status_code == HTTPStatus.OK
        assert len(ctx.captured_queries) <= _CONFLICT_QUERY_LIMIT, (
            f"Conflict detection used {len(ctx.captured_queries)} queries, "
            f"expected ≤ {_CONFLICT_QUERY_LIMIT}"
        )

    def test_overview_bounded_queries(
        self, authenticated_client, active_user, sphere, timetable_scale_data
    ):
        """Overview page should not double-run conflict detection."""
        event = timetable_scale_data["event"]
        sphere.managers.add(active_user)

        url = reverse("panel:timetable-overview", kwargs={"slug": event.slug})
        with CaptureQueriesContext(connection) as ctx:
            response = authenticated_client.get(url)

        assert response.status_code == HTTPStatus.OK
        assert len(ctx.captured_queries) <= _OVERVIEW_QUERY_LIMIT, (
            f"Overview used {len(ctx.captured_queries)} queries, "
            f"expected ≤ {_OVERVIEW_QUERY_LIMIT}"
        )
