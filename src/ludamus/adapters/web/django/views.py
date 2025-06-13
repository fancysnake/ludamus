import json
from datetime import UTC, date, datetime, timedelta
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any, Protocol
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
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from ludamus.adapters.oauth import oauth

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User
else:
    User = get_user_model()


TODAY = datetime.now(tz=UTC).date()


class UserReuqest(Protocol):
    user: User


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
    username = f'auth0|{sub.encode("UTF-8")}'
    if not isinstance(token["userinfo"].get("sub"), str) or "|" not in sub:
        raise TypeError

    if request.user.is_authenticated:
        pass
    elif user := User.objects.filter(username=username).first():
        django_login(request, user)
    else:
        user = User.objects.create_user(username=username)
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


class BaseUserForm(forms.ModelForm):  # type: ignore [type-arg]
    name = forms.CharField(label=_("Name"), required=True)
    birth_date = forms.DateField(
        label=_("Birth date"),
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
                "max": TODAY,
                "min": TODAY - timedelta(days=100 * 365.25),
            },
            format="%Y-%m-%d",
        ),
    )

    class Meta:
        model = User
        fields = ("name", "birth_date", "user_type")

    def clean_name(self) -> str:
        data: str = self.cleaned_data["name"]
        if not data:
            raise ValidationError(_("Please provide name."))

        return data


class UserForm(BaseUserForm):
    user_type = forms.CharField(
        initial=User.UserType.ACTIVE, widget=forms.HiddenInput()
    )

    def clean_birth_date(self) -> date:
        validation_error = "You need to be 16 years old to use this website."
        birth_date = self.cleaned_data["birth_date"]

        if not isinstance(birth_date, date) or birth_date >= datetime.now(
            tz=UTC
        ).date() - timedelta(days=16 * 365):
            raise ValidationError(validation_error)

        return birth_date

    class Meta:
        model = User
        fields = ("name", "email", "birth_date", "user_type")


class ConnectedUserForm(BaseUserForm):
    user_type = forms.CharField(
        initial=User.UserType.CONNECTED.value, widget=forms.HiddenInput()  # type: ignore [misc]
    )


class EditProfileView(LoginRequiredMixin, UpdateView):  # type: ignore [type-arg]
    template_name = "web_main/edit.html"
    form_class = UserForm
    success_url = "/"
    request: UserReuqest  # type: ignore [assignment]

    def get_object(
        self, queryset: QuerySet[User] | None = None  # noqa: ARG002
    ) -> User:
        if not isinstance(self.request.user, User):
            raise TypeError
        return self.request.user


class ConnectedView(LoginRequiredMixin, CreateView):  # type: ignore [type-arg]
    template_name = "web_main/connected.html"
    form_class = ConnectedUserForm
    success_url = "/profile/connected"
    request: UserReuqest  # type: ignore [assignment]
    object: User

    def get_context_data(  # type: ignore [explicit-any]
        self, **kwargs: Any  # noqa: ANN401
    ) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        connected_users = [
            {"user": connected, "form": ConnectedUserForm(instance=connected)}
            for connected in self.request.user.connected.all()
        ]
        context["connected_users"] = connected_users
        return context

    def get_queryset(self) -> QuerySet[User]:
        return User.objects.filter(
            user_type=User.UserType.CONNECTED, manager=self.request.user
        )

    def form_valid(self, form: forms.Form) -> HttpResponse:
        result = super().form_valid(form)
        self.object.manager = self.request.user
        self.object.username = f"connected|{token_urlsafe(50)}"
        self.object.password = token_urlsafe(50)
        self.object.save()
        return result


class EditConnectedView(LoginRequiredMixin, UpdateView):  # type: ignore [type-arg]
    template_name = "web_main/connected.html"
    form_class = ConnectedUserForm
    success_url = "/profile/connected"
    model = User


class DeleteConnectedView(LoginRequiredMixin, DeleteView):  # type: ignore [type-arg]
    model = User
    success_url = "/profile/connected"
