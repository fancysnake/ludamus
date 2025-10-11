import zoneinfo

import pytest


@pytest.fixture
def time_zone(settings):
    return zoneinfo.ZoneInfo(settings.TIME_ZONE)
