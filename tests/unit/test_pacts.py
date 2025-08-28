from datetime import UTC, date, datetime


class TestUserDTO:
    @staticmethod
    def test_age(freezer, complete_user_factory):
        freezer.move_to("2025-04-02")
        age = 24
        assert (
            complete_user_factory.build(
                date_joined=datetime.now(tz=UTC), birth_date=date(2001, 3, 1)
            ).age
            == age
        )

    @staticmethod
    def test_age_zero(authenticated_user_factory):
        assert authenticated_user_factory.build().age == 0
