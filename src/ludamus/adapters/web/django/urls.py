from django.urls import URLPattern, URLResolver, include, path

from . import views

app_name = "web"  # pylint: disable=invalid-name


auth0_urls = [
    path("do/login", views.Auth0LoginActionView.as_view(), name="login"),
    path(
        "do/login/callback",
        views.Auth0LoginCallbackActionView.as_view(),
        name="login-callback",
    ),
    path("do/logout", views.Auth0LogoutActionView.as_view(), name="logout"),
    path(
        "do/logout/redirect",
        views.Auth0LogoutRedirectActionView.as_view(),
        name="logout-redirect",
    ),
]

crowd_urls: list[URLPattern | URLResolver] = [
    path("auth0/", include((auth0_urls, "auth0"), namespace="auth0")),
    path(
        "login-required/", views.LoginRequiredPageView.as_view(), name="login-required"
    ),
    path("profile/", views.ProfilePageView.as_view(), name="profile"),
    path(
        "profile/connected-users/",
        views.ProfileConnectedUsersPageView.as_view(),
        name="profile-connected-users",
    ),
    path(
        "profile/connected-users/<str:slug>/do/update",
        views.ProfileConnectedUserUpdateActionView.as_view(),
        name="profile-connected-users-update",
    ),
    path(
        "profile/connected-users/<str:slug>/do/delete",
        views.ProfileConnectedUserDeleteActionView.as_view(),
        name="profile-connected-users-delete",
    ),
    path(
        "user/<slug:user_slug>/parts/discord-username",
        views.UserDiscordUsernameComponentView.as_view(),
        name="user-discord-username",
    ),
]

chronology_urls = [
    path("event/<str:slug>/", views.EventPageView.as_view(), name="event"),
    path(
        "session/<int:session_id>/enrollment/",
        views.SessionEnrollPageView.as_view(),
        name="session-enrollment",
    ),
    path(
        "event/<str:event_slug>/proposal/",
        views.EventProposalPageView.as_view(),
        name="event-proposal",
    ),
    path(
        "proposal/<int:proposal_id>/accept/",
        views.ProposalAcceptPageView.as_view(),
        name="proposal-accept",
    ),
    path(
        "event/<str:event_slug>/anonymous/do/activate",
        views.EventAnonymousActivateActionView.as_view(),
        name="event-anonymous-activate",
    ),
    path(
        "session/<int:session_id>/enrollment/anonymous",
        views.SessionEnrollmentAnonymousPageView.as_view(),
        name="session-enrollment-anonymous",
    ),
    path(
        "anonymous/do/load",
        views.AnonymousLoadActionView.as_view(),
        name="anonymous-load",
    ),
    path(
        "anonymous/do/reset/",
        views.AnonymousResetActionView.as_view(),
        name="anonymous-reset",
    ),
]

panel_urls = [
    path("", views.PanelIndexPageView.as_view(), name="index"),
    path("events/", views.PanelEventsPageView.as_view(), name="events"),
    path("users/", views.PanelUsersPageView.as_view(), name="users"),
    path("settings/", views.PanelSettingsPageView.as_view(), name="settings"),
    path(
        "event/do/create",
        views.PanelEventCreateActionView.as_view(),
        name="event-create",
    ),
    path(
        "event/<int:event_id>/do/update",
        views.PanelEventUpdateActionView.as_view(),
        name="event-update",
    ),
    path(
        "event/<int:event_id>/do/delete",
        views.PanelEventDeleteActionView.as_view(),
        name="event-delete",
    ),
    path(
        "role/do/create", views.PanelRoleCreateActionView.as_view(), name="role-create"
    ),
    path(
        "role/<int:role_id>/do/update",
        views.PanelRoleUpdateActionView.as_view(),
        name="role-update",
    ),
    path(
        "role/<int:role_id>/do/delete",
        views.PanelRoleDeleteActionView.as_view(),
        name="role-delete",
    ),
    path(
        "role/<int:role_id>/permissions/",
        views.PanelRolePermissionsPageView.as_view(),
        name="role-permissions",
    ),
    path(
        "role/<int:role_id>/permission/do/add",
        views.PanelRolePermissionAddActionView.as_view(),
        name="role-permission-add",
    ),
    path(
        "role/<int:role_id>/permission/do/remove",
        views.PanelRolePermissionRemoveActionView.as_view(),
        name="role-permission-remove",
    ),
]

urlpatterns = [
    path("", views.IndexPageView.as_view(), name="index"),
    path(
        "chronology/", include((chronology_urls, "chronology"), namespace="chronology")
    ),
    path("crowd/", include((crowd_urls, "crowd"), namespace="crowd")),
    path("panel/", include((panel_urls, "panel"), namespace="panel")),
    path(
        "theme/do/select", views.ThemeSelectionActionView.as_view(), name="theme-select"
    ),
]
