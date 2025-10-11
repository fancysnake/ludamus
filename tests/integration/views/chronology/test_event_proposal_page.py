from http import HTTPStatus
from unittest.mock import ANY

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Proposal, Tag, TagCategory
from tests.integration.utils import assert_response


class TestEventProposalPageView:
    URL_NAME = "web:chronology:event-proposal"

    def _get_url(self, slug: str) -> str:
        return reverse(self.URL_NAME, kwargs={"event_slug": slug})

    @pytest.mark.usefixtures("proposal_category")
    def test_get_ok(self, authenticated_client, event, faker, time_zone):
        event.proposal_start_time = faker.date_time_between(
            "-10d", "-1d", tzinfo=time_zone
        )
        event.proposal_end_time = faker.date_time_between(
            "+1d", "+10d", tzinfo=time_zone
        )
        event.save()
        response = authenticated_client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "confirmed_tags": {},
                "event": event,
                "form": ANY,
                "max_participants_limit": 20,
                "min_participants_limit": 2,
                "tag_categories": [],
            },
            template_name="chronology/propose_session.html",
        )

    @pytest.mark.usefixtures("proposal_category")
    def test_post_form_invalid(self, authenticated_client, event, faker, time_zone):
        event.proposal_start_time = faker.date_time_between(
            "-10d", "-1d", tzinfo=time_zone
        )
        event.proposal_end_time = faker.date_time_between(
            "+1d", "+10d", tzinfo=time_zone
        )
        event.save()
        response = authenticated_client.post(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "confirmed_tags": {},
                "event": event,
                "form": ANY,
                "max_participants_limit": 20,
                "min_participants_limit": 2,
                "tag_categories": [],
            },
            template_name="chronology/propose_session.html",
        )

    def test_post_ok(
        self,
        active_user,
        authenticated_client,
        event,
        faker,
        proposal_category,
        time_zone,
    ):
        event.proposal_start_time = faker.date_time_between(
            "-10d", "-1d", tzinfo=time_zone
        )
        event.proposal_end_time = faker.date_time_between(
            "+1d", "+10d", tzinfo=time_zone
        )
        event.save()
        data = {
            "title": faker.sentence(),
            "description": faker.text(),
            "requirements": faker.text(),
            "needs": faker.text(),
            "participants_limit": 6,
            "min_age": 3,  # PEGI 3
        }
        response = authenticated_client.post(self._get_url(event.slug), data=data)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    f"Session proposal '{data['title']}' submitted successfully!",
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        proposal = Proposal.objects.get()
        assert proposal.category == proposal_category
        assert proposal.host == active_user
        assert proposal.title == data["title"]
        assert proposal.description == data["description"]
        assert proposal.requirements == data["requirements"]
        assert proposal.needs == data["needs"]
        assert proposal.participants_limit == data["participants_limit"]
        assert proposal.min_age == data["min_age"]

    def test_post_ok_with_tags(
        self,
        active_user,
        authenticated_client,
        event,
        faker,
        proposal_category,
        time_zone,
    ):
        type_tag = TagCategory.objects.create(
            name="system", input_type=TagCategory.InputType.TYPE
        )
        select_tag = TagCategory.objects.create(
            name="availability", input_type=TagCategory.InputType.SELECT
        )
        proposal_category.tag_categories.add(type_tag)
        proposal_category.tag_categories.add(select_tag)
        tag1 = Tag.objects.create(name="vision", category=select_tag, confirmed=True)
        tag2 = Tag.objects.create(name="movement", category=select_tag, confirmed=True)
        Tag.objects.create(name="hearing", category=select_tag, confirmed=True)
        event.proposal_start_time = faker.date_time_between(
            "-10d", "-1d", tzinfo=time_zone
        )
        event.proposal_end_time = faker.date_time_between(
            "+1d", "+10d", tzinfo=time_zone
        )
        event.save()
        data = {
            "title": faker.sentence(),
            "description": faker.text(),
            "requirements": faker.text(),
            "needs": faker.text(),
            "participants_limit": 6,
            "min_age": 3,  # PEGI 3
            f"tags_{type_tag.id}": "D&D, Ravenloft",
            f"tags_{select_tag.id}": [str(tag1.id), str(tag2.id)],
        }
        response = authenticated_client.post(self._get_url(event.slug), data=data)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    f"Session proposal '{data['title']}' submitted successfully!",
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        proposal = Proposal.objects.get()
        assert proposal.category == proposal_category
        assert proposal.host == active_user
        assert proposal.title == data["title"]
        assert proposal.description == data["description"]
        assert proposal.requirements == data["requirements"]
        assert proposal.needs == data["needs"]
        assert proposal.participants_limit == data["participants_limit"]
        assert proposal.min_age == data["min_age"]
        assert sorted(proposal.tags.all().values_list("name", flat=True)) == [
            "D&D",
            "Ravenloft",
            "movement",
            "vision",
        ]
        assert Tag.objects.get(name="D&D", category=type_tag)
        assert Tag.objects.get(name="Ravenloft", category=type_tag)

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_event_not_found(self, authenticated_client, method):
        response = getattr(authenticated_client, method)(self._get_url("unknown"))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url=reverse("web:index"),
        )

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_event_proposal_inactive(
        self, authenticated_client, method, event, faker, time_zone
    ):
        event.proposal_start_time = faker.date_time_between(
            "-10d", "-5d", tzinfo=time_zone
        )
        event.proposal_end_time = faker.date_time_between(
            "-4d", "-2d", tzinfo=time_zone
        )

        response = getattr(authenticated_client, method)(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    "Proposal submission is not currently active for this event.",
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_event_missing_proposal_category(
        self, authenticated_client, method, event, faker, time_zone
    ):
        event.proposal_start_time = faker.date_time_between(
            "-10d", "-1d", tzinfo=time_zone
        )
        event.proposal_end_time = faker.date_time_between(
            "+1d", "+10d", tzinfo=time_zone
        )
        event.save()
        response = getattr(authenticated_client, method)(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    (
                        "No proposal category configured for this event. Please "
                        "contact the organizers."
                    ),
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
