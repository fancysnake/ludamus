from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import TimeSlot
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimeSlotDeleteActionView:
    """Tests for /panel/event/<slug>/cfp/time-slots/<pk>/do/delete action."""

    @staticmethod
    def get_url(event, slot_pk):
        return reverse(
            "panel:time-slot-delete", kwargs={"slug": event.slug, "slot_pk": slot_pk}
        )

    def test_get_not_allowed(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        slot = TimeSlot.objects.create(
            event=event,
            start_time=event.start_time,
            end_time=event.start_time.replace(hour=event.start_time.hour + 2),
        )

        response = authenticated_client.get(self.get_url(event, slot.pk))

        assert_response(response, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_post_redirects_anonymous_user_to_login(self, client, event, time_slot):
        url = self.get_url(event, time_slot.pk)

        response = client.post(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(
        self, authenticated_client, event, time_slot
    ):
        response = authenticated_client.post(self.get_url(event, time_slot.pk))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_deletes_time_slot(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        slot_pk = time_slot.pk

        response = authenticated_client.post(self.get_url(event, time_slot.pk))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Time slot deleted successfully.")],
            url=reverse("panel:time-slots", kwargs={"slug": event.slug}),
        )
        assert not TimeSlot.objects.filter(pk=slot_pk).exists()

    def test_post_succeeds_silently_for_nonexistent_slot(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(self.get_url(event, 99999))

        # Deleting nonexistent slot still redirects with success
        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Time slot deleted successfully.")],
            url=reverse("panel:time-slots", kwargs={"slug": event.slug}),
        )

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere, time_slot
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:time-slot-delete",
            kwargs={"slug": "nonexistent", "slot_pk": time_slot.pk},
        )

        response = authenticated_client.post(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )
