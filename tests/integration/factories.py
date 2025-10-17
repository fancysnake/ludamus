import factory
from factory.django import DjangoModelFactory
from faker import Faker

from ludamus.adapters.db.django.models import User
from ludamus.pacts import UserType

faker = Faker()


class CompleteUserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Faker("email")
    name = factory.Faker("name")
    username = factory.Faker("uuid4")
    user_type = UserType.ACTIVE


class AnonymousUserFactory(DjangoModelFactory):
    class Meta:
        model = User

    user_type = UserType.ANONYMOUS
    username = factory.Faker("uuid4")
    is_active = False
    slug = factory.LazyFunction(lambda: f"code_{faker.word()}")
