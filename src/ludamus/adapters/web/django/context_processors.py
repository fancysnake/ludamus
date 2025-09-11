from django.conf import settings
from django.http import HttpRequest

from ludamus.pacts import RootDAORequestProtocol, SiteDTO, SphereDTO


def sites(request: RootDAORequestProtocol) -> dict[str, SiteDTO | SphereDTO]:
    return {
        "root_site": request.root_dao.root_site,
        "current_site": request.root_dao.current_site,
        "current_sphere": request.root_dao.current_sphere,
    }


def support(request: HttpRequest) -> dict[str, str]:  # noqa: ARG001
    return {"SUPPORT_EMAIL": settings.SUPPORT_EMAIL}
