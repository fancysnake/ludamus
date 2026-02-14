from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.pacts import EventDTO, ProposalCategoryDTO, ProposalListItemDTO
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

DEFAULT_FILTERS = {
    "q": "",
    "statuses": [],
    "category_ids": [],
    "sort": "newest",
    "page_size": 10,
}


def _build_list_context(
    event,
    *,
    proposals,
    status_counts,
    total_count,
    filtered_count,
    filters=None,
    categories=None,
    page=1,
    total_pages=1,
    has_previous=False,
    has_next=False,
    pending_proposals=0,
    scheduled_sessions=0,
    total_proposals=0,
    hosts_count=0,
    rooms_count=0,
):
    return {
        "events": [EventDTO.model_validate(event)],
        "current_event": EventDTO.model_validate(event),
        "is_proposal_active": False,
        "stats": {
            "total_sessions": pending_proposals + scheduled_sessions,
            "scheduled_sessions": scheduled_sessions,
            "pending_proposals": pending_proposals,
            "hosts_count": hosts_count,
            "rooms_count": rooms_count,
            "total_proposals": total_proposals,
        },
        "active_nav": "proposals",
        "proposals": proposals,
        "status_counts": status_counts,
        "total_count": total_count,
        "filtered_count": filtered_count,
        "filters": filters or DEFAULT_FILTERS,
        "categories": categories or [],
        "page": page,
        "total_pages": total_pages,
        "has_previous": has_previous,
        "has_next": has_next,
    }


def _make_expected_item(proposal, status):
    return ProposalListItemDTO(
        pk=proposal.pk,
        title=proposal.title,
        description=proposal.description,
        host_name=proposal.host.name or proposal.host.username,
        host_id=proposal.host_id,
        category_name=proposal.category.name,
        category_id=proposal.category_id,
        status=status,
        creation_time=proposal.creation_time,
        session_id=proposal.session_id,
    )


def _status_counts(pending=0, rejected=0, unassigned=0, scheduled=0):
    return {
        "PENDING": pending,
        "REJECTED": rejected,
        "UNASSIGNED": unassigned,
        "SCHEDULED": scheduled,
    }


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

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[],
                status_counts=_status_counts(),
                total_count=0,
                filtered_count=0,
            ),
            template_name="panel/proposals.html",
        )

    def test_lists_proposals_for_event(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        p1 = ProposalFactory(category=category, title="Alpha Proposal")
        p2 = ProposalFactory(category=category, title="Beta Proposal")

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[
                    _make_expected_item(p2, "PENDING"),
                    _make_expected_item(p1, "PENDING"),
                ],
                status_counts=_status_counts(pending=2),
                total_count=2,
                filtered_count=2,
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=2,
                total_proposals=2,
                hosts_count=2,
            ),
            template_name="panel/proposals.html",
        )

    def test_shows_correct_status_pending(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        p = ProposalFactory(category=category, title="Pending One")

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[_make_expected_item(p, "PENDING")],
                status_counts=_status_counts(pending=1),
                total_count=1,
                filtered_count=1,
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=1,
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposals.html",
        )

    def test_shows_correct_status_rejected(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        p = ProposalFactory(category=category, title="Rejected One", rejected=True)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[_make_expected_item(p, "REJECTED")],
                status_counts=_status_counts(rejected=1),
                total_count=1,
                filtered_count=1,
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=1,
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposals.html",
        )

    def test_shows_correct_status_unassigned(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        p = ProposalFactory(category=category, title="Unassigned One", session=session)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[_make_expected_item(p, "UNASSIGNED")],
                status_counts=_status_counts(unassigned=1),
                total_count=1,
                filtered_count=1,
                categories=[ProposalCategoryDTO.model_validate(category)],
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposals.html",
        )

    def test_shows_correct_status_scheduled(
        self, authenticated_client, active_user, sphere, event, area
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        space = SpaceFactory(area=area)
        AgendaItemFactory(session=session, space=space)
        p = ProposalFactory(category=category, title="Scheduled One", session=session)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[_make_expected_item(p, "SCHEDULED")],
                status_counts=_status_counts(scheduled=1),
                total_count=1,
                filtered_count=1,
                categories=[ProposalCategoryDTO.model_validate(category)],
                scheduled_sessions=1,
                total_proposals=1,
                hosts_count=1,
                rooms_count=1,
            ),
            template_name="panel/proposals.html",
        )

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
        p_pending = ProposalFactory(category=category, title="Pending")
        ProposalFactory(category=category, title="Rejected", rejected=True)

        response = authenticated_client.get(self.get_url(event) + "?status=PENDING")

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[_make_expected_item(p_pending, "PENDING")],
                status_counts=_status_counts(pending=1, rejected=1),
                total_count=2,
                filtered_count=1,
                filters={**DEFAULT_FILTERS, "statuses": ["PENDING"]},
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=2,
                total_proposals=2,
                hosts_count=2,
            ),
            template_name="panel/proposals.html",
        )

    def test_filters_by_status_rejected(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        ProposalFactory(category=category, title="Pending")
        p_rejected = ProposalFactory(category=category, title="Rejected", rejected=True)

        response = authenticated_client.get(self.get_url(event) + "?status=REJECTED")

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[_make_expected_item(p_rejected, "REJECTED")],
                status_counts=_status_counts(pending=1, rejected=1),
                total_count=2,
                filtered_count=1,
                filters={**DEFAULT_FILTERS, "statuses": ["REJECTED"]},
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=2,
                total_proposals=2,
                hosts_count=2,
            ),
            template_name="panel/proposals.html",
        )

    def test_filters_by_multiple_statuses(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        p_pending = ProposalFactory(category=category, title="Pending")
        p_rejected = ProposalFactory(category=category, title="Rejected", rejected=True)
        ProposalFactory(category=category, title="Unassigned", session=session)

        response = authenticated_client.get(
            self.get_url(event) + "?status=PENDING&status=REJECTED"
        )

        # Sorted by newest: Rejected (created after Pending)
        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[
                    _make_expected_item(p_rejected, "REJECTED"),
                    _make_expected_item(p_pending, "PENDING"),
                ],
                status_counts=_status_counts(pending=1, rejected=1, unassigned=1),
                total_count=3,
                filtered_count=2,
                filters={**DEFAULT_FILTERS, "statuses": ["PENDING", "REJECTED"]},
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=2,
                total_proposals=3,
                hosts_count=3,
            ),
            template_name="panel/proposals.html",
        )

    def test_filters_by_category(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        cat1 = ProposalCategoryFactory(event=event, name="RPG")
        cat2 = ProposalCategoryFactory(event=event, name="Board")
        p_rpg = ProposalFactory(category=cat1, title="RPG Proposal")
        ProposalFactory(category=cat2, title="Board Proposal")

        response = authenticated_client.get(
            self.get_url(event) + f"?category={cat1.pk}"
        )

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[_make_expected_item(p_rpg, "PENDING")],
                status_counts=_status_counts(pending=1),
                total_count=1,
                filtered_count=1,
                filters={**DEFAULT_FILTERS, "category_ids": [cat1.pk]},
                # Categories ordered by name: Board < RPG
                categories=[
                    ProposalCategoryDTO.model_validate(cat2),
                    ProposalCategoryDTO.model_validate(cat1),
                ],
                pending_proposals=2,
                total_proposals=2,
                hosts_count=2,
            ),
            template_name="panel/proposals.html",
        )

    def test_filters_by_text_search(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        p_dragon = ProposalFactory(category=category, title="Dragon Quest Adventure")
        ProposalFactory(category=category, title="Space Odyssey")

        response = authenticated_client.get(self.get_url(event) + "?q=dragon")

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[_make_expected_item(p_dragon, "PENDING")],
                status_counts=_status_counts(pending=1),
                total_count=1,
                filtered_count=1,
                filters={**DEFAULT_FILTERS, "q": "dragon"},
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=2,
                total_proposals=2,
                hosts_count=2,
            ),
            template_name="panel/proposals.html",
        )

    def test_filters_by_host_search(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        host1 = UserFactory(name="Alice Smith")
        host2 = UserFactory(name="Bob Jones")
        p_alice = ProposalFactory(category=category, title="Alice Proposal", host=host1)
        ProposalFactory(category=category, title="Bob Proposal", host=host2)

        response = authenticated_client.get(self.get_url(event) + "?q=alice")

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[_make_expected_item(p_alice, "PENDING")],
                status_counts=_status_counts(pending=1),
                total_count=1,
                filtered_count=1,
                filters={**DEFAULT_FILTERS, "q": "alice"},
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=2,
                total_proposals=2,
                hosts_count=2,
            ),
            template_name="panel/proposals.html",
        )

    def test_sorts_by_title(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        p_zebra = ProposalFactory(category=category, title="Zebra")
        p_alpha = ProposalFactory(category=category, title="Alpha")

        response = authenticated_client.get(self.get_url(event) + "?sort=title")

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[
                    _make_expected_item(p_alpha, "PENDING"),
                    _make_expected_item(p_zebra, "PENDING"),
                ],
                status_counts=_status_counts(pending=2),
                total_count=2,
                filtered_count=2,
                filters={**DEFAULT_FILTERS, "sort": "title"},
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=2,
                total_proposals=2,
                hosts_count=2,
            ),
            template_name="panel/proposals.html",
        )

    def test_sorts_by_newest(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        p_first = ProposalFactory(category=category, title="First")
        p_second = ProposalFactory(category=category, title="Second")

        response = authenticated_client.get(self.get_url(event) + "?sort=newest")

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[
                    _make_expected_item(p_second, "PENDING"),
                    _make_expected_item(p_first, "PENDING"),
                ],
                status_counts=_status_counts(pending=2),
                total_count=2,
                filtered_count=2,
                filters={**DEFAULT_FILTERS, "sort": "newest"},
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=2,
                total_proposals=2,
                hosts_count=2,
            ),
            template_name="panel/proposals.html",
        )

    def test_paginates_results(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        page_size = 10  # default
        total = 25
        created = [
            ProposalFactory(category=category, title=f"Proposal {i:02d}")
            for i in range(total)
        ]

        # Newest first
        expected_all = [_make_expected_item(p, "PENDING") for p in reversed(created)]
        hosts_count = len({p.host_id for p in created})
        common = {
            "status_counts": _status_counts(pending=total),
            "total_count": total,
            "filtered_count": total,
            "categories": [ProposalCategoryDTO.model_validate(category)],
            "pending_proposals": total,
            "total_proposals": total,
            "hosts_count": hosts_count,
        }

        response_p1 = authenticated_client.get(self.get_url(event))
        response_p2 = authenticated_client.get(self.get_url(event) + "?page=2")
        response_p3 = authenticated_client.get(self.get_url(event) + "?page=3")

        assert_response(
            response_p1,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=expected_all[:page_size],
                page=1,
                total_pages=3,
                has_next=True,
                **common,
            ),
            template_name="panel/proposals.html",
        )
        assert_response(
            response_p2,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=expected_all[page_size : page_size * 2],
                page=2,
                total_pages=3,
                has_previous=True,
                has_next=True,
                **common,
            ),
            template_name="panel/proposals.html",
        )
        assert_response(
            response_p3,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=expected_all[page_size * 2 :],
                page=3,
                total_pages=3,
                has_previous=True,
                **common,
            ),
            template_name="panel/proposals.html",
        )

    def test_status_counts_unaffected_by_status_filter(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        p1 = ProposalFactory(category=category, title="Pending 1")
        p2 = ProposalFactory(category=category, title="Pending 2")
        ProposalFactory(category=category, title="Rejected", rejected=True)

        response = authenticated_client.get(self.get_url(event) + "?status=PENDING")

        # Sorted by newest: p2 was created after p1
        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[
                    _make_expected_item(p2, "PENDING"),
                    _make_expected_item(p1, "PENDING"),
                ],
                status_counts=_status_counts(pending=2, rejected=1),
                total_count=3,
                filtered_count=2,
                filters={**DEFAULT_FILTERS, "statuses": ["PENDING"]},
                categories=[ProposalCategoryDTO.model_validate(category)],
                pending_proposals=3,
                total_proposals=3,
                hosts_count=3,
            ),
            template_name="panel/proposals.html",
        )

    def test_invalid_page_param_does_not_crash(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?page=abc")

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[],
                status_counts=_status_counts(),
                total_count=0,
                filtered_count=0,
            ),
            template_name="panel/proposals.html",
        )

    def test_invalid_category_param_is_ignored(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?category=abc")

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[],
                status_counts=_status_counts(),
                total_count=0,
                filtered_count=0,
            ),
            template_name="panel/proposals.html",
        )

    def test_invalid_page_size_param_does_not_crash(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?page_size=abc")

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_list_context(
                event,
                proposals=[],
                status_counts=_status_counts(),
                total_count=0,
                filtered_count=0,
            ),
            template_name="panel/proposals.html",
        )
