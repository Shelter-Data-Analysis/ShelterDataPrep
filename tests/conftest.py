"""Collection-time bookkeeping that no single test can reach on its own.

The size of the collected suite is known once, when pytest finishes
collecting it, and a test running inside that suite cannot see it. The hook
below records the count and whether the run was narrowed, and the fixture
hands both to the one test that compares the count against the README.
"""

from __future__ import annotations

import pytest

COLLECTED = {"count": 0, "whole_suite": False}


def pytest_collection_modifyitems(session, config, items):
    COLLECTED["count"] = len(items)
    # -k, -m, --deselect, or a named node collects a subset, and a subset
    # compared against a count of the whole suite fails for the wrong reason.
    COLLECTED["whole_suite"] = not (config.option.keyword
                                    or config.option.markexpr
                                    or config.option.deselect
                                    or any("::" in arg for arg in config.args))


@pytest.fixture
def collected_suite():
    return dict(COLLECTED)
