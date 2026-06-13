"""pytest configuration for scholarly tests.

- Blocks real HTTP requests in scholarly test modules (safety net).
- Mocks time.sleep to avoid real delays in retry tests.
- Non-scholarly tests are unaffected.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch


# ── Network access guard ──

def _is_scholarly_test(item) -> bool:
    """Check if a test belongs to the scholarly test suite."""
    module_name = item.module.__name__ if hasattr(item, 'module') else ''
    return any(keyword in module_name for keyword in (
        'test_scholarly', 'test_journal_registry', 'test_citation_formatter',
    ))


@pytest.fixture(autouse=True)
def block_network_in_scholarly_tests(request):
    """Block real HTTP requests in scholarly tests.

    Scholarly tests MUST use mock injection on clients. If a test accidentally
    creates a real requests.Session, this fixture will fail fast with a clear
    error instead of making a real network call.
    """
    if not _is_scholarly_test(request.node):
        yield
        return

    import requests as requests_mod

    original_request = requests_mod.Session.request

    def _blocked(self, *args, **kwargs):
        raise RuntimeError(
            "Real HTTP request blocked in scholarly test. "
            "Scholarly tests must use mock injection on client sessions."
        )

    try:
        with patch.object(requests_mod.Session, 'request', side_effect=_blocked):
            yield
    finally:
        pass


@pytest.fixture(autouse=True)
def mock_sleep_in_scholarly_tests(request):
    """Mock time.sleep in scholarly tests to avoid real delays.

    Retry/backoff tests should inject their own sleeper, but this global
    mock ensures no test accidentally sleeps for real.
    """
    if not _is_scholarly_test(request.node):
        yield
        return

    import time as time_mod

    try:
        with patch.object(time_mod, 'sleep', return_value=None):
            yield
    finally:
        pass
