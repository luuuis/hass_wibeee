import sys

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    # should not be needed but for some reason Python already has in its cache the
    # site-packages/pytest_homeassistant_custom_component.testing_config.custom_components
    del sys.modules['custom_components']
