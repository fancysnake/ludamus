from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest

from ludamus.adapters.db.django.models import Sphere


def sites(request: HttpRequest) -> dict[str, Site | RequestSite | Sphere | None]:
    root_site = Site.objects.get(domain=settings.ROOT_DOMAIN)
    current_site = get_current_site(request)
    return {
        "root_site": root_site,
        "current_site": current_site,
        "current_sphere": getattr(current_site, "sphere", None),
    }


def support(request: HttpRequest) -> dict[str, str]:  # noqa: ARG001
    return {"SUPPORT_EMAIL": settings.SUPPORT_EMAIL}
