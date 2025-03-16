import sys

import pytest
from pytest_socket import enable_socket, socket_allow_hosts


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup():
    if sys.platform == 'win32':
        # hack to allow running tests in Win32:
        # https://github.com/MatthewFlamm/pytest-homeassistant-custom-component/issues/154#issuecomment-2065081783
        enable_socket()
        socket_allow_hosts(["127.0.0.1", "localhost", "::1"], allow_unix_socket=True)
    yield
