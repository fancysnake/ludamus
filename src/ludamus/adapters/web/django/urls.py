# 📁 webappexample/urls.py -----

from django.urls import path

from . import views

app_name = "web"  # pylint: disable=invalid-name

urlpatterns = [
    path("", views.index, name="index"),
    path("chronology/event/<str:slug>", views.EventView.as_view(), name="event"),
    path(
        "chronology/session/<int:session_id>/enroll-select",
        views.EnrollSelectView.as_view(),
        name="enroll-select",
    ),
    path(
        "chronology/session/<int:session_id>/enroll",
        views.EnrollSessionView.as_view(),
        name="enroll-session",
    ),
    path(
        "chronology/session/<int:session_id>/cancel",
        views.CancelEnrollmentView.as_view(),
        name="cancel-enrollment",
    ),
    path(
        "chronology/session/<int:session_id>/waiting-list",
        views.EnrollWaitingListView.as_view(),
        name="enroll-waiting-list",
    ),
    path(
        "chronology/session/<int:session_id>/cancel-waiting-list",
        views.CancelWaitingListView.as_view(),
        name="cancel-waiting-list",
    ),
    path(
        "chronology/event/<str:event_slug>/propose",
        views.ProposeSessionView.as_view(),
        name="propose-session",
    ),
    path(
        "chronology/event/<str:event_slug>/propose/<int:time_slot_id>",
        views.ProposeSessionView.as_view(),
        name="propose-session-slot",
    ),
    path(
        "chronology/proposal/<int:proposal_id>/accept",
        views.AcceptProposalPageView.as_view(),
        name="accept-proposal-page",
    ),
    path(
        "chronology/proposal/<int:proposal_id>/accept/confirm",
        views.AcceptProposalView.as_view(),
        name="accept-proposal",
    ),
    path("crowd/user/connected", views.ConnectedView.as_view(), name="connected"),
    path(
        "crowd/user/connected/<str:slug>",
        views.EditConnectedView.as_view(),
        name="connected-details",
    ),
    path(
        "crowd/user/connected/<str:slug>/delete",
        views.DeleteConnectedView.as_view(),
        name="connected-delete",
    ),
    path("crowd/user/edit", views.EditProfileView.as_view(), name="edit"),
    path("crowd/user/login", views.login, name="login"),
    path("crowd/user/login/callback", views.callback, name="callback"),
    path("crowd/user/logout", views.logout, name="logout"),
    path("redirect", views.redirect_view, name="redirect"),
]
