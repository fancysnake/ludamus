from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from tests.integration.conftest import (
    AgendaItemFactory,
    ProposalCategoryFactory,
    ProposalFactory,
    SessionFactory,
    SpaceFactory,
    UserFactory,
)
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestProposalsPageView:
    """Tests for /panel/event/<slug>/proposals/ view."""

    @staticmethod
    def get_url(event):
        return reverse("panel:proposals", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_ok_for_sphere_manager_with_no_proposals(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "panel/proposals.html"
        assert response.context_data["proposals"] == []
        assert response.context_data["active_nav"] == "proposals"

    def test_lists_proposals_for_event(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        p1 = ProposalFactory(category=category, title="Alpha Proposal")
        p2 = ProposalFactory(category=category, title="Beta Proposal")

        response = authenticated_client.get(self.get_url(event))

        proposals = response.context_data["proposals"]
        proposal_titles = {p.title for p in proposals}
        assert p1.title in proposal_titles
        assert p2.title in proposal_titles

    def test_shows_correct_status_pending(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        ProposalFactory(category=category, title="Pending One")

        response = authenticated_client.get(self.get_url(event))

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1
        assert proposals[0].status == "PENDING"

    def test_shows_correct_status_rejected(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        ProposalFactory(category=category, title="Rejected One", rejected=True)

        response = authenticated_client.get(self.get_url(event))

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1
        assert proposals[0].status == "REJECTED"

    def test_shows_correct_status_unassigned(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        ProposalFactory(category=category, title="Unassigned One", session=session)

        response = authenticated_client.get(self.get_url(event))

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1
        assert proposals[0].status == "UNASSIGNED"

    def test_shows_correct_status_scheduled(
        self, authenticated_client, active_user, sphere, event, area
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        space = SpaceFactory(area=area)
        AgendaItemFactory(session=session, space=space)
        ProposalFactory(category=category, title="Scheduled One", session=session)

        response = authenticated_client.get(self.get_url(event))

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1
        assert proposals[0].status == "SCHEDULED"

    def test_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:proposals", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_filters_by_status_pending(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        ProposalFactory(category=category, title="Pending")
        ProposalFactory(category=category, title="Rejected", rejected=True)

        response = authenticated_client.get(self.get_url(event) + "?status=PENDING")

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1
        assert proposals[0].title == "Pending"

    def test_filters_by_status_rejected(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        ProposalFactory(category=category, title="Pending")
        ProposalFactory(category=category, title="Rejected", rejected=True)

        response = authenticated_client.get(self.get_url(event) + "?status=REJECTED")

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1
        assert proposals[0].title == "Rejected"

    def test_filters_by_multiple_statuses(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        ProposalFactory(category=category, title="Pending")
        ProposalFactory(category=category, title="Rejected", rejected=True)
        ProposalFactory(category=category, title="Unassigned", session=session)

        response = authenticated_client.get(
            self.get_url(event) + "?status=PENDING&status=REJECTED"
        )

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1 + 1
        titles = {p.title for p in proposals}
        assert titles == {"Pending", "Rejected"}

    def test_filters_by_category(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        cat1 = ProposalCategoryFactory(event=event, name="RPG")
        cat2 = ProposalCategoryFactory(event=event, name="Board")
        ProposalFactory(category=cat1, title="RPG Proposal")
        ProposalFactory(category=cat2, title="Board Proposal")

        response = authenticated_client.get(
            self.get_url(event) + f"?category={cat1.pk}"
        )

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1
        assert proposals[0].title == "RPG Proposal"

    def test_filters_by_text_search(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        ProposalFactory(category=category, title="Dragon Quest Adventure")
        ProposalFactory(category=category, title="Space Odyssey")

        response = authenticated_client.get(self.get_url(event) + "?q=dragon")

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1
        assert proposals[0].title == "Dragon Quest Adventure"

    def test_filters_by_host_search(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        host1 = UserFactory(name="Alice Smith")
        host2 = UserFactory(name="Bob Jones")
        ProposalFactory(category=category, title="Alice Proposal", host=host1)
        ProposalFactory(category=category, title="Bob Proposal", host=host2)

        response = authenticated_client.get(self.get_url(event) + "?q=alice")

        proposals = response.context_data["proposals"]
        assert len(proposals) == 1
        assert proposals[0].title == "Alice Proposal"

    def test_sorts_by_title(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        ProposalFactory(category=category, title="Zebra")
        ProposalFactory(category=category, title="Alpha")

        response = authenticated_client.get(self.get_url(event) + "?sort=title")

        proposals = response.context_data["proposals"]
        assert proposals[0].title == "Alpha"
        assert proposals[1].title == "Zebra"

    def test_sorts_by_newest(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        ProposalFactory(category=category, title="First")
        ProposalFactory(category=category, title="Second")

        response = authenticated_client.get(self.get_url(event) + "?sort=newest")

        proposals = response.context_data["proposals"]
        assert proposals[0].title == "Second"
        assert proposals[1].title == "First"

    def test_paginates_results(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        page_size = 10  # default
        total = 25
        for i in range(total):
            ProposalFactory(category=category, title=f"Proposal {i:02d}")

        response_p1 = authenticated_client.get(self.get_url(event))
        response_p2 = authenticated_client.get(self.get_url(event) + "?page=2")
        response_p3 = authenticated_client.get(self.get_url(event) + "?page=3")

        assert len(response_p1.context["proposals"]) == page_size
        assert len(response_p2.context["proposals"]) == page_size
        assert len(response_p3.context["proposals"]) == total - page_size * 2

    def test_status_counts_unaffected_by_status_filter(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        ProposalFactory(category=category, title="Pending 1")
        ProposalFactory(category=category, title="Pending 2")
        ProposalFactory(category=category, title="Rejected", rejected=True)

        response = authenticated_client.get(self.get_url(event) + "?status=PENDING")

        status_counts = response.context_data["status_counts"]
        assert status_counts["PENDING"] == 1 + 1  # two pending proposals
        assert status_counts["REJECTED"] == 1
        assert response.context_data["total_count"] == 1 + 1 + 1  # all proposals

    def test_invalid_page_param_does_not_crash(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?page=abc")

        assert response.status_code == HTTPStatus.OK

    def test_invalid_category_param_is_ignored(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?category=abc")

        assert response.status_code == HTTPStatus.OK

    def test_invalid_page_size_param_does_not_crash(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?page_size=abc")

        assert response.status_code == HTTPStatus.OK
