from ludamus.adapters.db.django.models import (
    Event,
    EventKind,
    EventSettings,
    KIND_DEFAULTS,
    get_setting,
)


class TestEventKind:
    def test_meetup_value(self):
        assert EventKind.MEETUP == "meetup"

    def test_convention_value(self):
        assert EventKind.CONVENTION == "convention"

    def test_choices(self):
        choices = EventKind.choices
        assert ("meetup", "Meetup") in choices
        assert ("convention", "Convention") in choices


class TestKindDefaults:
    def test_meetup_defaults(self):
        assert KIND_DEFAULTS[EventKind.MEETUP] == {"allow_session_images": True}

    def test_convention_defaults(self):
        assert KIND_DEFAULTS[EventKind.CONVENTION] == {"allow_session_images": False}


class TestEventSettings:
    def test_str(self, faker):
        name = faker.word()
        assert (
            str(EventSettings(event=Event(name=name)))
            == f"Settings for {name}"
        )


class TestGetSetting:
    def test_returns_kind_default_when_no_settings(self):
        event = Event(kind=EventKind.MEETUP)
        # No settings attached, should fall back to kind defaults
        result = get_setting(event, "allow_session_images")
        assert result is True

    def test_returns_convention_default(self):
        event = Event(kind=EventKind.CONVENTION)
        result = get_setting(event, "allow_session_images")
        assert result is False

    def test_returns_none_for_unknown_key(self):
        event = Event(kind=EventKind.MEETUP)
        result = get_setting(event, "nonexistent_key")
        assert result is None

    def test_event_get_setting_method(self):
        event = Event(kind=EventKind.MEETUP)
        assert event.get_setting("allow_session_images") is True

    def test_event_default_kind_is_meetup(self):
        event = Event()
        assert event.kind == EventKind.MEETUP
