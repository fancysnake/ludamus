from datetime import timedelta
from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Tag, TagCategory
from tests.integration.conftest import (
    AgendaItemFactory,
    AreaFactory,
    ProposalCategoryFactory,
    ProposalFactory,
    SessionFactory,
    SpaceFactory,
    TimeSlotFactory,
    VenueFactory,
)
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestProposalDetailPageView:
    """Tests for GET /panel/event/<slug>/proposals/<id>/."""

    @staticmethod
    def get_url(event, proposal):
        return reverse(
            "panel:proposal-detail",
            kwargs={"slug": event.slug, "proposal_id": proposal.pk},
        )

    @staticmethod
    def get_list_url(event):
        return reverse("panel:proposals", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category)
        url = self.get_url(event, proposal)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_shows_proposal_details(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(
            category=category, host=active_user, title="My Proposal"
        )

        response = authenticated_client.get(self.get_url(event, proposal))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["proposal"].title == "My Proposal"
        assert response.context_data["host"].pk == active_user.pk
        assert response.context_data["status"] == "PENDING"
        assert "tags" in response.context_data
        assert "time_slots" in response.context_data

    def test_shows_host_info(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, host=active_user)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert response.status_code == HTTPStatus.OK
        host = response.context_data["host"]
        assert host.name == active_user.name
        assert host.email == active_user.email

    def test_shows_tags(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        tag_category = TagCategory.objects.create(name="Genre", icon="dice")
        tag = Tag.objects.create(category=tag_category, name="RPG")
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, host=active_user)
        proposal.tags.add(tag)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert response.status_code == HTTPStatus.OK
        tag_names = [t.name for t in response.context_data["tags"]]
        assert "RPG" in tag_names

    def test_redirects_on_proposal_not_found(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:proposal-detail", kwargs={"slug": event.slug, "proposal_id": 99999}
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=self.get_list_url(event),
        )

    def test_pending_status_for_proposal_without_session(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=False)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["status"] == "PENDING"

    def test_rejected_status_for_rejected_proposal(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=True)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["status"] == "REJECTED"

    def test_scheduled_status_for_proposal_with_agenda_item(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        proposal = ProposalFactory(category=category, session=session)
        venue = VenueFactory(event=event)
        area = AreaFactory(venue=venue)
        space = SpaceFactory(area=area)
        AgendaItemFactory(session=session, space=space)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["status"] == "SCHEDULED"

    def test_unassigned_status_for_proposal_with_session_but_no_agenda_item(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        proposal = ProposalFactory(category=category, session=session)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["status"] == "UNASSIGNED"

    def test_shows_only_proposal_time_slots_not_all_event_time_slots(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        base = event.start_time
        ts1 = TimeSlotFactory(
            event=event, start_time=base, end_time=base + timedelta(hours=2)
        )
        TimeSlotFactory(
            event=event,
            start_time=base + timedelta(hours=3),
            end_time=base + timedelta(hours=5),
        )
        TimeSlotFactory(
            event=event,
            start_time=base + timedelta(hours=6),
            end_time=base + timedelta(hours=8),
        )
        proposal = ProposalFactory(category=category, host=active_user)
        proposal.time_slots.add(ts1)

        response = authenticated_client.get(self.get_url(event, proposal))

        time_slots = response.context_data["time_slots"]
        assert len(time_slots) == 1
        assert time_slots[0].pk == ts1.pk
