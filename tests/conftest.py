import asyncio
import sys

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    pass


@pytest.fixture(autouse=True)
def auto_override_eventloop():
    if sys.platform == "win32":
        # workaround for AttributeError: 'ProactorEventLoop' object has no attribute '_ssock'
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
