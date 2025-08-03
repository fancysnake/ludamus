from datetime import date

from ludamus.adapters.db.django.models import Event, Space, Sphere, User


class TestUser:
    @staticmethod
    def test_get_short_name():
        assert User(name="John Smith").get_short_name() == "John"

    @staticmethod
    def test_age(freezer):
        freezer.move_to("2025-04-02")
        age = 24
        assert User(birth_date=date(2001, 3, 1)).age == age

    @staticmethod
    def test_age_zero():
        assert User().age == 0


class TestEvent:
    @staticmethod
    def test_str(faker):
        name = faker.word()
        assert str(Event(name=name)) == name


class TestSphere:
    @staticmethod
    def test_str(faker):
        name = faker.word()
        assert str(Sphere(name=name)) == name


class TestSpace:
    @staticmethod
    def test_str():
        assert str(Space(name="room", id=7)) == "room (7)"
