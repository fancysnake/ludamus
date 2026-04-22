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
]
