from polyfactory import Require, Use
from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.pytest_plugin import register_fixture

from ludamus.pacts import UserDTO, UserType


@register_fixture
class AuthenticatedUserFactory(ModelFactory[UserDTO]):
    is_active = True
    is_authenticated = True
    user_type = UserType.ACTIVE
    name = ""
    birth_date = None
    email = ""


@register_fixture
class CompleteUserFactory(AuthenticatedUserFactory):
    name = Use(ModelFactory.__faker__.name)
    birth_date = Use(ModelFactory.__faker__.date_between, "-100y", "-16y")
    email = Use(ModelFactory.__faker__.email)


@register_fixture
class UnderageUserFactory(AuthenticatedUserFactory):
    name = Use(ModelFactory.__faker__.name)
    birth_date = Use(ModelFactory.__faker__.date_between, "-15y", "-1y")
    email = Use(ModelFactory.__faker__.email)


@register_fixture
class UnderageConnectedUserFactory(UnderageUserFactory):
    user_type = UserType.CONNECTED
    manager_id = Require()
    email = ""
