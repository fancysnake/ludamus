"""URL patterns for the timetable panel feature."""

from django.urls import path

from ludamus.gates.web.django.chronology.panel import views

timetable_urlpatterns = [
    path("", views.TimetablePageView.as_view(), name="timetable"),
    path(
        "parts/sessions/",
        views.TimetableSessionListPartView.as_view(),
        name="timetable-sessions-part",
    ),
    path(
        "parts/session/<int:pk>/",
        views.TimetableSessionDetailPartView.as_view(),
        name="timetable-session-detail-part",
    ),
    path(
        "parts/grid/", views.TimetableGridPartView.as_view(), name="timetable-grid-part"
    ),
    path(
        "parts/conflicts/",
        views.TimetableConflictsPartView.as_view(),
        name="timetable-conflicts-part",
    ),
    path("do/assign/", views.TimetableAssignView.as_view(), name="timetable-assign"),
    path(
        "do/unassign/", views.TimetableUnassignView.as_view(), name="timetable-unassign"
    ),
    path("log/", views.TimetableLogPageView.as_view(), name="timetable-log"),
]
