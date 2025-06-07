from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest


def sites(request: HttpRequest) -> dict[str, Site | RequestSite]:
    root_site = Site.objects.get(domain=settings.ROOT_DOMAIN)
    current_site = get_current_site(request)
    return {"root_site": root_site, "current_site": current_site}
