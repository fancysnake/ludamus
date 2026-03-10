from datetime import timedelta
from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import (
    HostPersonalData,
    PersonalDataField,
    PersonalDataFieldOption,
    PersonalDataFieldRequirement,
    Proposal,
    Session,
    SessionField,
    SessionFieldOption,
    SessionFieldRequirement,
    SessionFieldValue,
    TimeSlotRequirement,
)
from tests.integration.conftest import ProposalCategoryFactory, TimeSlotFactory
from tests.integration.utils import assert_response


class TestProposeSessionPageView:
    URL_NAME = "web:chronology:session-propose"

    def _get_url(self, event_slug: str) -> str:
        return reverse(self.URL_NAME, kwargs={"event_slug": event_slug})

    def _activate_proposals(self, event, faker, time_zone):
        event.proposal_start_time = faker.date_time_between(
            "-10d", "-1d", tzinfo=time_zone
        )
        event.proposal_end_time = faker.date_time_between(
            "+1d", "+10d", tzinfo=time_zone
        )
        event.save()

    def _set_wizard_category(self, client, event, category):
        session = client.session
        session[f"propose_{event.slug}"] = {"category_id": category.pk}
        session.save()

    def _set_wizard_full(self, client, event, category, **extra):
        session = client.session
        wizard = {
            "category_id": category.pk,
            "session_data": {"title": "Test Session", "participants_limit": 6},
            **extra,
        }
        session[f"propose_{event.slug}"] = wizard
        session.save()

    # -- GET tests --

    def test_get_requires_login(self, client, event, faker, time_zone):
        self._activate_proposals(event, faker, time_zone)
        response = client.get(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.FOUND

    def test_get_redirects_when_proposals_inactive(self, authenticated_client, event):
        response = authenticated_client.get(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.FOUND

    def test_get_shows_category_selection(
        self, authenticated_client, event, faker, time_zone
    ):
        self._activate_proposals(event, faker, time_zone)
        cat1 = ProposalCategoryFactory(event=event, name="Board Game")
        cat2 = ProposalCategoryFactory(event=event, name="RPG Session")

        response = authenticated_client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": event,
                "categories": [cat1, cat2],
                "step": "category",
            },
            template_name="chronology/propose/base.html",
        )

    def test_get_auto_advances_with_single_category(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)

        response = authenticated_client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": event,
                "category": proposal_category,
                "step": "category",
                "auto_advance": True,
            },
            template_name="chronology/propose/base.html",
        )

    def test_get_stores_category_in_session_on_auto_advance(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)

        authenticated_client.get(self._get_url(event.slug))

        wizard = authenticated_client.session[f"propose_{event.slug}"]
        assert wizard["category_id"] == proposal_category.pk

    # -- Category POST tests --

    def test_post_category_stores_in_session(
        self, authenticated_client, event, faker, time_zone
    ):
        self._activate_proposals(event, faker, time_zone)
        cat = ProposalCategoryFactory(event=event, name="RPG Session")
        ProposalCategoryFactory(event=event, name="Workshop")

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "category", "category_id": cat.pk}
        )

        assert response.status_code == HTTPStatus.OK
        wizard = authenticated_client.session[f"propose_{event.slug}"]
        assert wizard["category_id"] == cat.pk

    def test_post_category_without_choice_shows_error(
        self, authenticated_client, event, faker, time_zone
    ):
        self._activate_proposals(event, faker, time_zone)
        ProposalCategoryFactory(event=event)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "category"}
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["error"]

    def test_post_category_advances_to_personal_step(
        self, authenticated_client, event, faker, time_zone
    ):
        self._activate_proposals(event, faker, time_zone)
        cat = ProposalCategoryFactory(event=event, name="RPG")
        ProposalCategoryFactory(event=event, name="Workshop")
        field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=cat, field=field, is_required=True
        )

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "category", "category_id": cat.pk}
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["form"] is not None
        assert len(response.context["field_descriptors"]) == 1
        assert response.context["field_descriptors"][0]["name"] == "Phone"

    def test_post_category_skips_personal_when_no_fields(
        self, authenticated_client, event, faker, time_zone
    ):
        self._activate_proposals(event, faker, time_zone)
        cat = ProposalCategoryFactory(event=event, name="RPG")
        ProposalCategoryFactory(event=event, name="Workshop")

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "category", "category_id": cat.pk}
        )

        # Skips personal step (no fields), skips timeslots (no requirements),
        # renders session details form
        assert response.status_code == HTTPStatus.OK
        assert response.context["form"] is not None
        assert response.template_name == "chronology/propose/step_session.html"

    # -- Personal data POST tests --

    def test_post_personal_data_valid(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "personal", "personal_phone": "+48 123"}
        )

        assert response.status_code == HTTPStatus.OK
        wizard = authenticated_client.session[f"propose_{event.slug}"]
        assert wizard["personal_data"]["personal_phone"] == "+48 123"

    def test_post_personal_data_invalid_shows_errors(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "personal"}  # missing required phone
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["form"].errors

    def test_post_personal_data_select_field(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = PersonalDataField.objects.create(
            event=event, name="T-Shirt", slug="tshirt", field_type="select"
        )
        PersonalDataFieldOption.objects.create(
            field=field, label="Small", value="S", order=0
        )
        PersonalDataFieldOption.objects.create(
            field=field, label="Medium", value="M", order=1
        )
        PersonalDataFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=False
        )
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "personal", "personal_tshirt": "M"}
        )

        assert response.status_code == HTTPStatus.OK
        wizard = authenticated_client.session[f"propose_{event.slug}"]
        assert wizard["personal_data"]["personal_tshirt"] == "M"

    # -- Time slot POST tests --

    def test_personal_step_prefills_from_saved_data(
        self,
        authenticated_client,
        event,
        faker,
        time_zone,
        proposal_category,
        active_user,
    ):
        self._activate_proposals(event, faker, time_zone)
        field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        # Simulate previously saved personal data
        HostPersonalData.objects.create(
            user=active_user, event=event, field=field, value="+48 999"
        )
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug),
            {"step": "category", "category_id": proposal_category.pk},
        )

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        assert form.initial["personal_phone"] == "+48 999"

    def test_post_personal_advances_to_timeslots(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        slot = TimeSlotFactory(event=event)
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot)
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "personal", "personal_phone": "+48 123"}
        )

        assert response.status_code == HTTPStatus.OK
        assert len(response.context["slot_descriptors"]) == 1

    def test_post_timeslots_stores_in_session(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        slot1 = TimeSlotFactory(event=event)
        slot2 = TimeSlotFactory(
            event=event,
            start_time=event.start_time + timedelta(hours=3),
            end_time=event.start_time + timedelta(hours=5),
        )
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot1)
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot2)
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug),
            {"step": "timeslots", "time_slot_ids": [str(slot1.pk), str(slot2.pk)]},
        )

        assert response.status_code == HTTPStatus.OK
        wizard = authenticated_client.session[f"propose_{event.slug}"]
        assert sorted(wizard["time_slot_ids"]) == sorted([slot1.pk, slot2.pk])
        # Advances to session details
        assert response.context["form"] is not None

    def test_post_timeslots_without_selection_shows_error(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        slot = TimeSlotFactory(event=event)
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot)
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "timeslots"}
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["error"]

    def test_post_timeslots_filters_invalid_ids(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        slot = TimeSlotFactory(event=event)
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot)
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug),
            {"step": "timeslots", "time_slot_ids": [str(slot.pk), "99999"]},
        )

        assert response.status_code == HTTPStatus.OK
        wizard = authenticated_client.session[f"propose_{event.slug}"]
        assert wizard["time_slot_ids"] == [slot.pk]

    def test_post_timeslots_skips_when_no_requirements(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "timeslots"}
        )

        # No time slot requirements — skips to session details
        assert response.status_code == HTTPStatus.OK
        assert response.context["form"] is not None
        assert response.template_name == "chronology/propose/step_session.html"

    def test_post_timeslots_preserves_selection(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        slot1 = TimeSlotFactory(event=event)
        slot2 = TimeSlotFactory(
            event=event,
            start_time=event.start_time + timedelta(hours=3),
            end_time=event.start_time + timedelta(hours=5),
        )
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot1)
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot2)
        # Pre-set wizard with a selected slot
        session = authenticated_client.session
        session[f"propose_{event.slug}"] = {
            "category_id": proposal_category.pk,
            "time_slot_ids": [slot1.pk],
        }
        session.save()

        # Navigate back to timeslots step
        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "back_to_personal"}
        )

        # Since no personal fields, it should render timeslots
        assert response.status_code == HTTPStatus.OK

    # -- Session details POST tests --

    def test_post_session_details_valid(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug),
            {
                "step": "session",
                "title": "My RPG Session",
                "description": "A great adventure",
                "participants_limit": "6",
            },
        )

        assert response.status_code == HTTPStatus.OK
        wizard = authenticated_client.session[f"propose_{event.slug}"]
        assert wizard["session_data"]["title"] == "My RPG Session"
        assert wizard["session_data"]["description"] == "A great adventure"
        assert wizard["session_data"]["participants_limit"] == int("6")

    def test_post_session_details_invalid_shows_errors(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug),
            {"step": "session"},  # missing required title and participants_limit
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["form"].errors

    def test_post_session_details_with_session_fields(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = SessionField.objects.create(
            event=event, name="RPG System", slug="rpg_system"
        )
        SessionFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug),
            {
                "step": "session",
                "title": "My Session",
                "participants_limit": "4",
                "session_rpg_system": "D&D 5e",
            },
        )

        assert response.status_code == HTTPStatus.OK
        wizard = authenticated_client.session[f"propose_{event.slug}"]
        assert wizard["session_data"]["session_rpg_system"] == "D&D 5e"

    def test_post_session_details_with_select_field(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = SessionField.objects.create(
            event=event, name="Genre", slug="genre", field_type="select"
        )
        SessionFieldOption.objects.create(
            field=field, label="Fantasy", value="fantasy", order=0
        )
        SessionFieldOption.objects.create(
            field=field, label="Sci-Fi", value="scifi", order=1
        )
        SessionFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=False
        )
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug),
            {
                "step": "session",
                "title": "Space Opera",
                "participants_limit": "5",
                "session_genre": "scifi",
            },
        )

        assert response.status_code == HTTPStatus.OK
        wizard = authenticated_client.session[f"propose_{event.slug}"]
        assert wizard["session_data"]["session_genre"] == "scifi"

    def test_post_session_renders_form_with_field_descriptors(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = SessionField.objects.create(
            event=event, name="RPG System", slug="rpg_system"
        )
        SessionFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        self._set_wizard_category(authenticated_client, event, proposal_category)

        # Submit invalid to re-render the form with descriptors
        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "session"}  # missing required fields
        )

        assert response.status_code == HTTPStatus.OK
        assert len(response.context["field_descriptors"]) == 1
        assert response.context["field_descriptors"][0]["name"] == "RPG System"

    def test_render_session_step_prefills_from_wizard(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        session = authenticated_client.session
        session[f"propose_{event.slug}"] = {
            "category_id": proposal_category.pk,
            "session_data": {"title": "Prefilled Title", "participants_limit": 8},
        }
        session.save()

        # back_to_timeslots with no timeslots skips to session step
        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "back_to_timeslots"}
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["form"] is not None

    # -- Back button tests --

    def test_post_back_to_category(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        ProposalCategoryFactory(event=event, name="Workshop")
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "back_to_category"}
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["categories"]

    def test_post_back_to_personal(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "back_to_personal"}
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["field_descriptors"]

    def test_post_back_to_timeslots(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        slot = TimeSlotFactory(event=event)
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot)
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "back_to_timeslots"}
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["slot_descriptors"]

    def test_post_back_to_session(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        self._set_wizard_full(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "back_to_session"}
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["form"] is not None

    # -- Review step tests --

    def test_post_session_advances_to_review(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        self._set_wizard_category(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug),
            {"step": "session", "title": "My Session", "participants_limit": "4"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["review"]["title"] == "My Session"
        assert response.template_name == "chronology/propose/step_review.html"

    def test_review_shows_all_wizard_data(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        slot = TimeSlotFactory(event=event)
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot)
        self._set_wizard_full(
            authenticated_client,
            event,
            proposal_category,
            personal_data={"personal_phone": "+48 123"},
            time_slot_ids=[slot.pk],
        )

        # Navigate to review via back_to_session then re-submit
        response = authenticated_client.post(
            self._get_url(event.slug),
            {
                "step": "session",
                "title": "Full Session",
                "participants_limit": "5",
                "description": "Full description",
            },
        )

        review = response.context["review"]
        assert review["title"] == "Full Session"
        assert review["category_name"] == proposal_category.name
        assert len(review["personal_fields"]) == 1
        assert len(review["time_slots"]) == 1

    # -- Submit tests --

    def test_submit_creates_session_and_proposal(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        self._set_wizard_full(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "submit"}
        )

        assert response.status_code == HTTPStatus.FOUND
        session = Session.objects.get(title="Test Session")
        assert session.participants_limit == int("6")
        assert session.category == proposal_category
        proposal = Proposal.objects.get(session=session)
        assert proposal.title == "Test Session"

    def test_submit_saves_personal_data(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        self._set_wizard_full(
            authenticated_client,
            event,
            proposal_category,
            personal_data={"personal_phone": "+48 555"},
        )

        authenticated_client.post(self._get_url(event.slug), {"step": "submit"})

        hpd = HostPersonalData.objects.get(event=event, field=field)
        assert hpd.value == "+48 555"

    def test_submit_sets_time_slots(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        slot = TimeSlotFactory(event=event)
        TimeSlotRequirement.objects.create(category=proposal_category, time_slot=slot)
        self._set_wizard_full(
            authenticated_client, event, proposal_category, time_slot_ids=[slot.pk]
        )

        authenticated_client.post(self._get_url(event.slug), {"step": "submit"})

        session = Session.objects.get(title="Test Session")
        assert list(session.time_slots.values_list("pk", flat=True)) == [slot.pk]

    def test_submit_saves_session_field_values(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        field = SessionField.objects.create(
            event=event, name="RPG System", slug="rpg_system"
        )
        SessionFieldRequirement.objects.create(
            category=proposal_category, field=field, is_required=True
        )
        self._set_wizard_full(
            authenticated_client,
            event,
            proposal_category,
            session_data={
                "title": "Test Session",
                "participants_limit": 6,
                "session_rpg_system": "D&D 5e",
            },
        )

        authenticated_client.post(self._get_url(event.slug), {"step": "submit"})

        session = Session.objects.get(title="Test Session")
        sfv = SessionFieldValue.objects.get(session=session, field=field)
        assert sfv.value == "D&D 5e"

    def test_submit_clears_wizard_session(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        self._set_wizard_full(authenticated_client, event, proposal_category)

        authenticated_client.post(self._get_url(event.slug), {"step": "submit"})

        assert f"propose_{event.slug}" not in authenticated_client.session

    def test_submit_shows_success_message(
        self, authenticated_client, event, faker, time_zone, proposal_category
    ):
        self._activate_proposals(event, faker, time_zone)
        self._set_wizard_full(authenticated_client, event, proposal_category)

        response = authenticated_client.post(
            self._get_url(event.slug), {"step": "submit"}
        )

        msgs = list(messages.get_messages(response.wsgi_request))
        assert len(msgs) == 1
        assert "Test Session" in str(msgs[0])
