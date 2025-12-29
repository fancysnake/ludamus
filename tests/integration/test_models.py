import pytest
from django.core.exceptions import ValidationError

from ludamus.adapters.db.django.models import TimeSlot


class TestTimeSlot:
    def test_validate_unique_ok(self, event, faker):
        TimeSlot.objects.create(
            event=event,
            start_time=faker.date_time_between("+1h", "+2h"),
            end_time=faker.date_time_between("+3h", "+4h"),
        )
        TimeSlot(
            event=event,
            start_time=faker.date_time_between("+5h", "+6h"),
            end_time=faker.date_time_between("+7h", "+8h"),
        ).full_clean()

    def test_validate_unique_error_start_inside(self, event, faker):
        TimeSlot.objects.create(
            event=event,
            start_time=faker.date_time_between("+3h", "+4h"),
            end_time=faker.date_time_between("+7h", "+8h"),
        )
        with pytest.raises(ValidationError):
            TimeSlot(
                event=event,
                start_time=faker.date_time_between("+1h", "+2h"),
                end_time=faker.date_time_between("+5h", "+6h"),
            ).full_clean()

    def test_validate_unique_error_end_inside(self, event, faker):
        TimeSlot.objects.create(
            event=event,
            start_time=faker.date_time_between("+3h", "+4h"),
            end_time=faker.date_time_between("+7h", "+8h"),
        )
        with pytest.raises(ValidationError):
            TimeSlot(
                event=event,
                start_time=faker.date_time_between("+5h", "+6h"),
                end_time=faker.date_time_between("+9h", "+10h"),
            ).full_clean()

    def test_validate_unique_error_contains(self, event, faker):
        TimeSlot.objects.create(
            event=event,
            start_time=faker.date_time_between("+1h", "+2h"),
            end_time=faker.date_time_between("+7h", "+8h"),
        )
        with pytest.raises(ValidationError):
            TimeSlot(
                event=event,
                start_time=faker.date_time_between("+3h", "+4h"),
                end_time=faker.date_time_between("+5h", "+6h"),
            ).full_clean()
