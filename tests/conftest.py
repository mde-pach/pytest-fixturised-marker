import pytest

pytest_plugins = ["pytester"]

MARKED_CONFTEST = """
import pytest


@pytest.mark.slow
@pytest.fixture
def heavy():
    return "heavy"


@pytest.fixture
@pytest.mark.slow
def also_heavy():
    return "also heavy"


@pytest.fixture
def wraps_heavy(heavy):
    return heavy


@pytest.mark.skip(reason="no docker here")
@pytest.fixture
def needs_docker():
    return "docker"
"""


@pytest.fixture(autouse=True)
def registered_markers(pytester: pytest.Pytester) -> None:
    pytester.makeini(
        """
        [pytest]
        markers =
            slow: takes a long time
            network: touches the network
        """
    )


@pytest.fixture
def marked_fixtures(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(MARKED_CONFTEST)
