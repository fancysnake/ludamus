import logging

import pytest
from django.template import Context, Template

from tests.template_checks import (
    MissingTemplateVariableError,
    MissingTemplateVariableFilter,
)


@pytest.fixture
def _template_check():
    logger = logging.getLogger("django.template")
    original_level = logger.level
    f = MissingTemplateVariableFilter()
    logger.setLevel(logging.DEBUG)
    logger.addFilter(f)
    yield
    logger.removeFilter(f)
    logger.setLevel(original_level)


@pytest.mark.usefixtures("_template_check")
class TestDefaultFilterOnSimpleVar:
    def test_simple_var_with_default_does_not_raise(self):
        template = Template('{{ edit|default:"fallback" }}')
        # Should not raise MissingTemplateVariableError
        template.render(Context({}))

    def test_dotted_var_with_default_still_raises(self):
        template = Template('{{ object.edit|default:"fallback" }}')
        with pytest.raises(MissingTemplateVariableError):
            template.render(Context({"object": object()}))

    def test_simple_var_without_default_still_raises(self):
        template = Template("{{ edit }}")
        with pytest.raises(MissingTemplateVariableError):
            template.render(Context({}))
