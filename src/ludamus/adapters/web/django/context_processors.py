from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings

from ludamus.adapters.web.django.entities import UserInfo

if TYPE_CHECKING:
    from django.http import HttpRequest

    from ludamus.adapters.web.django.middlewares import RootRepositoryRequest


def sites(request: RootRepositoryRequest) -> dict[str, Any]:
    # Context processor may run during error handling before middleware completes
    if not hasattr(request, "context") or not hasattr(
        request, "di"
    ):  # pragma: no cover
        return {
            "root_site": None,
            "current_site": None,
            "current_sphere": None,
            "is_sphere_manager": False,
        }

    sphere_repository = request.di.uow.spheres
    root_sphere = sphere_repository.read(request.context.root_sphere_id)
    current_sphere = sphere_repository.read(request.context.current_sphere_id)

    is_sphere_manager = False
    if request.user.is_authenticated and request.context.current_user_slug:
        is_sphere_manager = sphere_repository.is_manager(
            current_sphere.pk, request.context.current_user_slug
        )

    return {
        "root_site": sphere_repository.read_site(root_sphere.pk),
        "current_site": sphere_repository.read_site(current_sphere.pk),
        "current_sphere": current_sphere,
        "is_sphere_manager": is_sphere_manager,
    }


def support(request: HttpRequest) -> dict[str, str]:  # noqa: ARG001
    return {"SUPPORT_EMAIL": settings.SUPPORT_EMAIL}


def static_version(request: HttpRequest) -> dict[str, str]:  # noqa: ARG001
    return {"STATIC_VERSION": settings.STATIC_VERSION}


def current_user(request: RootRepositoryRequest) -> dict[str, Any]:
    # Context processor may run during error handling before middleware completes
    if (
        not hasattr(request, "context")
        or not hasattr(request, "di")
        or not request.context.current_user_slug
    ):
        return {"current_user": None, "current_connected_users": []}

    user_dto = request.di.uow.active_users.read(request.context.current_user_slug)
    return {
        "current_user": user_dto,
        "current_user_info": UserInfo.from_user_dto(user_dto),
        "current_connected_users": [
            UserInfo.from_user_dto(u)
            for u in request.di.uow.connected_users.read_all(
                request.context.current_user_slug
            )
        ],
    }
