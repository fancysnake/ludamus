import logging
import zoneinfo

import pytest

from tests.template_checks import MissingTemplateVariableFilter


@pytest.fixture(autouse=True)
def _fail_on_missing_template_variables():
    """Raise exception when template variables cannot be resolved.

    Django silently swallows AttributeError when accessing missing
    methods/properties on template objects. This fixture ensures
    such errors are caught during tests.
    """
    logger = logging.getLogger("django.template")
    original_level = logger.level
    filter_instance = MissingTemplateVariableFilter()

    logger.setLevel(logging.DEBUG)
    logger.addFilter(filter_instance)

    yield

    logger.removeFilter(filter_instance)
    logger.setLevel(original_level)


@pytest.fixture
def time_zone(settings):
    return zoneinfo.ZoneInfo(settings.TIME_ZONE)


@pytest.fixture(autouse=True)
def english_language(settings):
    settings.LANGUAGE_CODE = "en"
