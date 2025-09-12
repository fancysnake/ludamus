from django.contrib.sites.models import Site

from ludamus.pacts import SiteDTO, SphereDTO


class NotFoundError(Exception): ...


class RootDAO:
    def __init__(self, domain: str, root_domain: str) -> None:
        try:
            self._current_site = Site.objects.select_related("sphere").get(
                domain=domain
            )
        except Site.DoesNotExist as exception:
            raise NotFoundError from exception
        self._root_site = Site.objects.get(domain=root_domain)
        self._current_sphere = self._current_site.sphere

    @property
    def current_site(self) -> SiteDTO:
        return SiteDTO.model_validate(self._current_site)

    @property
    def current_sphere(self) -> SphereDTO:
        return SphereDTO.model_validate(self._current_sphere)

    @property
    def root_site(self) -> SiteDTO:
        return SiteDTO.model_validate(self._root_site)

    @property
    def allowed_domains(self) -> list[str]:
        return list(Site.objects.values_list("domain", flat=True))
