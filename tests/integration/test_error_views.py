from http import HTTPStatus

import pytest

from ludamus.adapters.web.django.error_views import custom_404, custom_500


@pytest.mark.django_db
class TestCustom404:

    @staticmethod
    def test_returns_404_status_code(rf):
        request = rf.get("/nonexistent-page/")
        response = custom_404(request, None)
        assert response.status_code == HTTPStatus.NOT_FOUND

    @staticmethod
    def test_uses_404_dynamic_template(rf):
        request = rf.get("/nonexistent-page/")
        response = custom_404(request, None)
        assert response.template_name == "404_dynamic.html"
        assert response.status_code == HTTPStatus.NOT_FOUND

    @staticmethod
    def test_context_contains_required_fields(rf):
        request = rf.get("/nonexistent-page/")
        response = custom_404(request, None)
        context = response.context_data

        assert "error_code" in context
        assert context["error_code"] == HTTPStatus.NOT_FOUND
        assert "title" in context
        assert "message" in context
        assert "subtitle" in context
        assert "icon" in context

    @staticmethod
    def test_selects_random_message(rf):
        responses = []
        for _ in range(10):
            request = rf.get("/nonexistent-page/")
            response = custom_404(request, None)
            context = response.context_data
            responses.append(context["title"])

        unique_responses = set(responses)
        assert len(unique_responses) > 1 or len(responses) == 1

    @staticmethod
    def test_message_structure_validity(rf):
        request = rf.get("/nonexistent-page/")
        response = custom_404(request, None)
        context = response.context_data

        assert isinstance(context["title"], str)
        assert context["title"]
        assert isinstance(context["message"], str)
        assert context["message"]
        assert isinstance(context["subtitle"], str)
        assert context["subtitle"]
        assert isinstance(context["icon"], str)
        assert context["icon"]


@pytest.mark.django_db
class TestCustom500:
    @staticmethod
    def test_returns_500_status_code(rf):
        request = rf.get("/test/")
        response = custom_500(request)
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @staticmethod
    def test_uses_500_dynamic_template(rf):
        request = rf.get("/test/")
        response = custom_500(request)
        assert response.template_name == "500_dynamic.html"
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @staticmethod
    def test_context_contains_required_fields(rf):
        request = rf.get("/test/")
        response = custom_500(request)
        context = response.context_data

        assert "error_code" in context
        assert context["error_code"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert "title" in context
        assert "message" in context
        assert "subtitle" in context
        assert "icon" in context

    @staticmethod
    def test_selects_random_message(rf):
        responses = []
        for _ in range(10):
            request = rf.get("/test/")
            response = custom_500(request)
            context = response.context_data
            responses.append(context["title"])

        unique_responses = set(responses)
        assert len(unique_responses) > 1 or len(responses) == 1

    @staticmethod
    def test_message_structure_validity(rf):
        request = rf.get("/test/")
        response = custom_500(request)
        context = response.context_data

        assert isinstance(context["title"], str)
        assert context["title"]
        assert isinstance(context["message"], str)
        assert context["message"]
        assert isinstance(context["subtitle"], str)
        assert context["subtitle"]
        assert isinstance(context["icon"], str)
        assert context["icon"]


@pytest.mark.django_db
class TestErrorViewsIntegration:
    @staticmethod
    def test_404_and_500_have_different_error_codes(rf):
        request = rf.get("/test/")

        response_404 = custom_404(request, None)
        response_500 = custom_500(request)

        assert response_404.context_data["error_code"] == HTTPStatus.NOT_FOUND
        assert (
            response_500.context_data["error_code"] == HTTPStatus.INTERNAL_SERVER_ERROR
        )
        assert response_404.status_code == HTTPStatus.NOT_FOUND
        assert response_500.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
