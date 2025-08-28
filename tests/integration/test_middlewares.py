from unittest.mock import Mock, patch

import pytest
from django.http import HttpResponseRedirect
from django.urls import reverse

from ludamus.adapters.web.django.exceptions import RedirectError
from ludamus.adapters.web.django.middlewares import (
    RedirectErrorMiddleware,
    RootMiddleware,
)
from ludamus.pacts import SphereDTO


@pytest.fixture(name="get_response_mock")
def get_response_mock_fixture():
    return Mock()


class TestSphereMiddleware:

    @pytest.fixture
    @staticmethod
    def middleware(get_response_mock):
        return RootMiddleware(get_response_mock)

    @pytest.mark.django_db
    @staticmethod
    def test_successful_sphere_lookup(
        get_response_mock, middleware, rf, sphere, authenticated_user_factory
    ):
        request = rf.get("/")
        request.META["HTTP_HOST"] = sphere.site.domain
        request.user = authenticated_user_factory.build()

        sphere.site.sphere = sphere

        middleware(request)

        assert request.root_dao.current_sphere == SphereDTO(
            name=sphere.name, pk=sphere.id
        )
        assert request.user_dao.user == request.user
        get_response_mock.assert_called_once_with(request)

    @pytest.mark.django_db
    @staticmethod
    def test_site_does_not_exist_redirects(
        middleware, get_response_mock, rf, settings, sphere
    ):
        settings.ALLOWED_HOSTS.append("nonexistent.example.com")
        request = rf.get("/")
        request.META["HTTP_HOST"] = "nonexistent.example.com"

        with patch("ludamus.adapters.web.django.middlewares.messages") as mock_messages:
            response = middleware(request)

            assert isinstance(response, HttpResponseRedirect)
            expected_url = f"http://{sphere.site.domain}{reverse('web:index')}"
            assert response.url == expected_url
            mock_messages.error.assert_called_once()
            get_response_mock.assert_not_called()


class TestRedirectErrorMiddleware:
    @pytest.fixture
    @staticmethod
    def middleware(get_response_mock):
        return RedirectErrorMiddleware(get_response_mock)

    @staticmethod
    def test_normal_request_processing(middleware, get_response_mock, rf):

        request = rf.get("/")

        middleware(request)

        get_response_mock.assert_called_once_with(request)

    @staticmethod
    def test_redirect_error_with_error_message(middleware, rf):
        request = rf.get("/")
        error_url = "/error-redirect/"
        error_message = "Test error message"
        exception = RedirectError(url=error_url, error=error_message)

        with patch(
            "ludamus.adapters.web.django.middlewares.messages.error"
        ) as mock_messages_error:
            response = middleware.process_exception(request, exception)

            assert isinstance(response, HttpResponseRedirect)
            assert response.url == error_url
            mock_messages_error.assert_called_once_with(request, error_message)

    @staticmethod
    def test_redirect_error_with_warning_message(middleware, rf):

        request = rf.get("/")
        error_url = "/warning-redirect/"
        warning_message = "Test warning message"
        exception = RedirectError(url=error_url, warning=warning_message)

        with patch(
            "ludamus.adapters.web.django.middlewares.messages.warning"
        ) as mock_messages_warning:
            response = middleware.process_exception(request, exception)

            assert isinstance(response, HttpResponseRedirect)
            assert response.url == error_url
            mock_messages_warning.assert_called_once_with(request, warning_message)

    @staticmethod
    def test_redirect_error_with_both_error_and_warning(middleware, rf):

        request = rf.get("/")
        error_url = "/both-messages-redirect/"
        error_message = "Test error message"
        warning_message = "Test warning message"
        exception = RedirectError(
            url=error_url, error=error_message, warning=warning_message
        )

        with (
            patch(
                "ludamus.adapters.web.django.middlewares.messages.error"
            ) as mock_messages_error,
            patch(
                "ludamus.adapters.web.django.middlewares.messages.warning"
            ) as mock_messages_warning,
        ):
            response = middleware.process_exception(request, exception)

            assert isinstance(response, HttpResponseRedirect)
            assert response.url == error_url
            mock_messages_error.assert_called_once_with(request, error_message)
            mock_messages_warning.assert_called_once_with(request, warning_message)

    @staticmethod
    def test_redirect_error_without_messages(middleware, rf):

        request = rf.get("/")
        error_url = "/no-message-redirect/"
        exception = RedirectError(url=error_url)

        with (
            patch(
                "ludamus.adapters.web.django.middlewares.messages.error"
            ) as mock_messages_error,
            patch(
                "ludamus.adapters.web.django.middlewares.messages.warning"
            ) as mock_messages_warning,
        ):
            response = middleware.process_exception(request, exception)

            assert isinstance(response, HttpResponseRedirect)
            assert response.url == error_url
            mock_messages_error.assert_not_called()
            mock_messages_warning.assert_not_called()

    @staticmethod
    def test_non_redirect_error_returns_none(middleware, rf):

        request = rf.get("/")
        exception = ValueError("Not a redirect error")

        response = middleware.process_exception(request, exception)

        assert response is None
