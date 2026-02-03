"""URL configuration for ludamus project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/

Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))

"""

from typing import NoReturn

from django.conf import settings
from django.contrib import admin
from django.http import HttpRequest  # noqa: TC002  # used in debug view
from django.urls import include, path

urlpatterns = [
    path("", include("ludamus.adapters.web.django.urls", namespace="web")),
    path("panel/", include("ludamus.gates.web.django.urls", namespace="panel")),
    path("admin/", admin.site.urls),
    path("page/", include("django.contrib.flatpages.urls")),
]

handler404 = (  # pylint: disable=invalid-name
    "ludamus.adapters.web.django.error_views.custom_404"
)
handler500 = (  # pylint: disable=invalid-name
    "ludamus.adapters.web.django.error_views.custom_500"
)

if settings.DEBUG:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]

    # Debug URLs to test error pages
    def _trigger_500(request: HttpRequest) -> NoReturn:  # noqa: ARG001
        raise Exception(  # noqa: TRY002  # pylint: disable=broad-exception-raised
            "Test 500 error"
        )

    from ludamus.adapters.web.django.error_views import custom_404, custom_500

    urlpatterns += [
        path("404/", lambda r: custom_404(r, None)),  # type: ignore[list-item]
        path("500/", custom_500),  # type: ignore[list-item]
        path("500-real/", _trigger_500),  # type: ignore[list-item]
    ]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
