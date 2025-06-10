import json
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import TYPE_CHECKING
from urllib.parse import quote_plus, urlencode

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import UpdateView

from ludamus.adapters.oauth import oauth

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User
else:
    User = get_user_model()


THIS_YEAR = datetime.now(tz=UTC).year


def login(request: HttpRequest) -> HttpResponse:
    root_domain = Site.objects.get(domain=settings.ROOT_DOMAIN).domain
    next_path = request.GET.get("next")
    if request.get_host() != root_domain:
        return redirect(
            f'{request.scheme}://{root_domain}{reverse("web:login")}?next={next_path}'
        )

    return oauth.auth0.authorize_redirect(  # type: ignore [no-any-return]
        request,
        request.build_absolute_uri(reverse("web:callback") + f"?next={next_path}"),
    )


def callback(request: HttpRequest) -> HttpResponse:
    token = oauth.auth0.authorize_access_token(request)
    if not isinstance(token.get("userinfo"), dict):
        raise TypeError

    sub = token["userinfo"].get("sub")
    if not isinstance(token["userinfo"].get("sub"), str) or "|" not in sub:
        raise TypeError

    if request.user.is_authenticated:
        pass
    elif user := User.objects.filter(auth0_user_id=sub).first():
        django_login(request, user)
    else:
        user = User.objects.create_user(
            username=sha256(sub.encode("UTF-8")).hexdigest(), auth0_user_id=sub
        )
        django_login(request, user)
        return redirect(request.build_absolute_uri(reverse("web:edit")))

    next_path = request.GET.get("next")
    return redirect(next_path or request.build_absolute_uri(reverse("web:index")))


def logout(request: HttpRequest) -> HttpResponse:
    django_logout(request)
    root_domain = Site.objects.get(domain=settings.ROOT_DOMAIN).domain
    last = get_current_site(request).domain
    return_to = f'{request.scheme}://{root_domain}{reverse("web:redirect")}?last={last}'

    return redirect(
        f"https://{settings.AUTH0_DOMAIN}/v2/logout?"
        + urlencode(
            {"returnTo": return_to, "client_id": settings.AUTH0_CLIENT_ID},
            quote_via=quote_plus,
        )
    )


def redirect_view(request: HttpRequest) -> HttpResponse:
    redirect_url = reverse("web:index")
    if last := request.GET.get("last"):
        redirect_url = f"{request.scheme}://{last}{redirect_url}"

    return redirect(redirect_url)


def index(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(
        request,
        "web_main/index.html",
        context={"pretty": json.dumps(request.session.get("user"), indent=4)},
    )


class UsernameForm(forms.ModelForm):  # type: ignore [type-arg]
    username = forms.CharField(
        help_text=_(
            "This is your public name that will be visible for everyone in the events "
            "you organize and participate in."
        ),
        label=_("Username"),
        max_length=150,
    )
    email = forms.EmailField(required=True)
    birth_date = forms.DateField(
        label=_("Birth date"),
        widget=forms.SelectDateWidget(
            years=range(THIS_YEAR, THIS_YEAR - 100, -1),
            attrs={"class": "form-select w-auto d-inline-block"},
        ),
    )

    class Meta:
        model = User
        fields = ("username", "email", "birth_date")

    def clean_birth_date(self) -> date:
        validation_error = "You need to be 16 years old to use this website."
        birth_date = self.cleaned_data["birth_date"]

        if not isinstance(birth_date, date) or birth_date >= datetime.now(
            tz=UTC
        ).date() - timedelta(days=16 * 365):
            raise ValidationError(validation_error)

        return birth_date


class UsernameView(LoginRequiredMixin, UpdateView):  # type: ignore [type-arg]
    template_name = "web_main/edit.html"
    form_class = UsernameForm
    success_url = "/"

    def get_object(
        self, queryset: QuerySet[User] | None = None  # noqa: ARG002
    ) -> User:
        if not isinstance(self.request.user, User):
            raise TypeError
        return self.request.user
