from django.conf import settings
from django.http import HttpRequest

from ludamus.pacts import RootRequestProtocol, SiteDTO, SphereDTO


def sites(request: RootRequestProtocol) -> dict[str, SiteDTO | SphereDTO]:
    sphere_repository = request.uow.spheres
    root_sphere = sphere_repository.read(request.context.root_sphere_id)
    current_sphere = sphere_repository.read(request.context.current_sphere_id)
    return {
        "root_site": sphere_repository.read_site(root_sphere.pk),
        "current_site": sphere_repository.read_site(current_sphere.pk),
        "current_sphere": current_sphere,
    }


def support(request: HttpRequest) -> dict[str, str]:  # noqa: ARG001
    return {"SUPPORT_EMAIL": settings.SUPPORT_EMAIL}
