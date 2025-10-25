from datetime import datetime

from ludamus.adapters.db.django.models import (
    DEFAULT_NAME,
    AgendaItem,
    DomainEnrollmentConfig,
    EnrollmentConfig,
    Event,
    Proposal,
    ProposalCategory,
    Session,
    SessionParticipation,
    SessionParticipationStatus,
    Space,
    Sphere,
    Tag,
    TagCategory,
    TimeSlot,
    User,
    UserEnrollmentConfig,
)


class TestSphere:
    def test_str(self, faker):
        name = faker.word()

        assert str(Sphere(name=name)) == name


class TestEnrollmentConfig:
    def test_str(self, faker):
        name = faker.word()

        assert (
            str(EnrollmentConfig(event=Event(name=name)))
            == f"Enrollment config for {name}"
        )


class TestUserEnrollmentConfig:
    def test_str(self, faker):
        email = faker.email()
        allowed_slots = faker.random_int(min=1)

        assert (
            str(UserEnrollmentConfig(user_email=email, allowed_slots=allowed_slots))
            == f"{email}: {allowed_slots} people enrollment limit"
        )


class TestDomainEnrollmentConfig:
    def test_str(self, faker):
        domain = faker.domain_name()
        slots = faker.random_int(min=1, max=100)

        assert str(
            DomainEnrollmentConfig(domain=domain, allowed_slots_per_user=slots)
        ) == (f"@{domain}: {slots} people enrollment limit per account")


class TestSpace:
    def test_str(self, faker):
        name = faker.word()
        pk = faker.random_int(min=1)

        assert str(Space(name=name, id=pk)) == f"{name} ({pk})"


class TestTimeSlot:
    def test_str(self, faker, time_zone):
        pk = faker.random_int(min=1)

        assert (
            str(
                TimeSlot(
                    id=pk,
                    start_time=datetime(2025, 1, 2, 3, 4, tzinfo=time_zone),
                    end_time=datetime(2025, 1, 2, 5, 6, tzinfo=time_zone),
                )
            )
            == f"2025-01-02 03:04 - 05:06 ({pk})"
        )

    def test_str_different_days(self, faker, time_zone):
        pk = faker.random_int(min=1)

        assert (
            str(
                TimeSlot(
                    id=pk,
                    start_time=datetime(2025, 1, 2, 3, 4, tzinfo=time_zone),
                    end_time=datetime(2025, 5, 6, 7, 8, tzinfo=time_zone),
                )
            )
            == f"2025-01-02 03:04 - 2025-05-06 07:08 ({pk})"
        )


class TestTagCategory:
    def test_str(self, faker):
        name = faker.word()

        assert str(TagCategory(name=name)) == name


class TestTag:
    def test_str(self, faker):
        name = faker.word()

        assert str(Tag(name=name)) == name


class TestSession:
    def test_str(self, faker):
        title = faker.word()

        assert str(Session(title=title)) == title


class TestAgendaItem:
    def test_str(self, faker):
        title = faker.sentence()
        name = faker.name()

        assert (
            str(
                AgendaItem(
                    session_confirmed=True,
                    session=Session(title=title, presenter_name=name),
                )
            )
            == f"{title} by {name} (True)"
        )


class TestProposalCategory:
    def test_str(self, faker):
        name = faker.word()
        pk = faker.random_int(min=1)

        assert str(ProposalCategory(name=name, id=pk)) == f"{name} ({pk})"


class TestProposal:
    def test_str(self, faker):
        title = faker.word()

        assert str(Proposal(title=title)) == title


class TestSessionParticipation:
    def test_str(self, faker):
        username = faker.user_name()
        title = faker.word()

        assert (
            str(
                SessionParticipation(
                    user=User(username=username),
                    status=SessionParticipationStatus.CONFIRMED,
                    session=Session(title=title),
                )
            )
            == f"{username} confirmed on {title}"
        )


class TestUser:
    def test_get_full_name_no_name(self):
        user = User()

        assert user.get_full_name() == DEFAULT_NAME

    def test_get_full_name(self, faker):
        user = User(name=faker.name())

        assert user.get_full_name() == user.name
