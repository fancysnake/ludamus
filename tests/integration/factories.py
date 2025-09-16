import factory
from factory.django import DjangoModelFactory

from ludamus.adapters.db.django.models import User


class CompleteUserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Faker("email")
    name = factory.Faker("name")
    username = factory.Faker("uuid4")
    user_type = User.UserType.ACTIVE


class AnonymousUserFactory(DjangoModelFactory):
    class Meta:
        model = User

    user_type = User.UserType.ANONYMOUS
    username = factory.Faker("uuid4")
    is_active = False
    slug = factory.Faker("word")
