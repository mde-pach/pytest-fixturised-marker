import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest

from pytest_fixturised_marker._dependencies import _dropping

RECORDING_CONFTEST = """
import pathlib

import pytest


def record(event):
    with pathlib.Path("events.txt").open("a") as handle:
        handle.write(event + "\\n")


@pytest.fixture
def tracker():
    record("tracker")


@pytest.fixture
def other_tracker():
    record("other tracker")


@pytest.mark.usefixtures("tracker")
@pytest.fixture
def marked():
    record("marked")
    return "marked"


@pytest.mark.usefixtures("tracker")
@pytest.fixture
def marked_yield():
    record("yield setup")
    yield "yielded"
    record("yield teardown")


@pytest.fixture
def wraps_marked(marked):
    return marked
"""


def events(pytester: pytest.Pytester) -> list[str]:
    return (pytester.path / "events.txt").read_text().splitlines()


@pytest.fixture
def recording_fixtures(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(RECORDING_CONFTEST)


@pytest.mark.usefixtures("recording_fixtures")
def test_named_fixture_is_set_up(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(marked): assert marked == 'marked'")

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert events(pytester) == ["tracker", "marked"]


@pytest.mark.usefixtures("recording_fixtures")
def test_named_fixture_is_set_up_for_transitive_users(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(wraps_marked): assert wraps_marked == 'marked'")

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert events(pytester) == ["tracker", "marked"]


@pytest.mark.usefixtures("recording_fixtures")
def test_yield_fixture_still_tears_down(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(marked_yield): assert marked_yield == 'yielded'")

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert events(pytester) == ["tracker", "yield setup", "yield teardown"]


@pytest.mark.usefixtures("recording_fixtures")
def test_the_test_does_not_have_to_request_the_named_fixture(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_it(marked, request):
            assert "tracker" in request.fixturenames
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_several_named_fixtures_are_set_up(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        RECORDING_CONFTEST
        + """

@pytest.mark.usefixtures("tracker", "other_tracker")
@pytest.fixture
def needs_both():
    record("both")
    return None
"""
    )
    pytester.makepyfile("def test_it(needs_both): pass")

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert events(pytester) == ["tracker", "other tracker", "both"]


def test_a_fixture_requesting_itself_by_name_is_ignored(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.usefixtures("resource")
        @pytest.fixture
        def resource():
            return "resource"
        """
    )
    pytester.makepyfile("def test_it(resource): assert resource == 'resource'")

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_scope_mismatch_is_reported_by_pytest(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.fixture(scope="function")
        def short_lived():
            return None


        @pytest.mark.usefixtures("short_lived")
        @pytest.fixture(scope="session")
        def long_lived():
            return None
        """
    )
    pytester.makepyfile("def test_it(long_lived): pass")

    result = pytester.runpytest()

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*ScopeMismatch*"])


def test_dropping_passes_through_a_plain_function() -> None:
    wrapped = _dropping(lambda value: value, ["extra"])

    assert wrapped(value=1, extra="dropped") == 1


def test_dropping_keeps_a_generator_a_generator() -> None:
    def source(value: int) -> Iterator[int]:
        yield value

    wrapped = _dropping(source, ["extra"])

    assert list(wrapped(value=1, extra="dropped")) == [1]


def test_dropping_keeps_a_coroutine_a_coroutine() -> None:
    async def source(value: int) -> int:
        return value

    wrapped = _dropping(source, ["extra"])

    assert asyncio.run(wrapped(value=1, extra="dropped")) == 1


def test_dropping_keeps_an_async_generator_an_async_generator() -> None:
    async def source(value: int) -> AsyncIterator[int]:
        yield value

    async def collect() -> list[int]:
        return [item async for item in _dropping(source, ["extra"])(value=1, extra="dropped")]

    assert asyncio.run(collect()) == [1]


def test_an_unknown_name_is_reported_by_pytest(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.usefixtures("nonexistent")
        @pytest.fixture
        def marked():
            return None
        """
    )
    pytester.makepyfile("def test_it(marked): pass")

    result = pytester.runpytest()

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*fixture 'nonexistent' not found*"])


@pytest.mark.usefixtures("recording_fixtures")
def test_an_autouse_fixture_can_name_others(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest


        @pytest.mark.usefixtures("tracker")
        @pytest.fixture(autouse=True)
        def always():
            return None


        def test_it(): pass
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert events(pytester) == ["tracker"]


def test_a_name_already_in_the_signature_is_not_set_up_twice(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        RECORDING_CONFTEST
        + """

@pytest.mark.usefixtures("tracker")
@pytest.fixture
def declares_it_too(tracker):
    record("declares")
    return None
"""
    )
    pytester.makepyfile("def test_it(declares_it_too): pass")

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert events(pytester) == ["tracker", "declares"]


def test_stacked_usefixtures_marks_accumulate(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        RECORDING_CONFTEST
        + """

@pytest.mark.usefixtures("tracker")
@pytest.mark.usefixtures("other_tracker")
@pytest.fixture
def stacked():
    record("stacked")
    return None
"""
    )
    pytester.makepyfile("def test_it(stacked): pass")

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert sorted(events(pytester)) == ["other tracker", "stacked", "tracker"]


def test_a_parametrized_fixture_keeps_its_parameter(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        RECORDING_CONFTEST
        + """

@pytest.mark.usefixtures("tracker")
@pytest.fixture(params=[1, 2])
def parametrised(request):
    return request.param
"""
    )
    pytester.makepyfile("def test_it(parametrised): assert parametrised in (1, 2)")

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


def test_a_fixture_defined_in_a_class_is_still_bound(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(RECORDING_CONFTEST)
    pytester.makepyfile(
        """
        import pytest


        class TestThings:
            @pytest.mark.usefixtures("tracker")
            @pytest.fixture
            def bound(self):
                assert isinstance(self, TestThings)
                return "bound"

            def test_it(self, bound):
                assert bound == "bound"
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert events(pytester) == ["tracker"]


def test_a_renamed_fixture_can_name_others(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        RECORDING_CONFTEST
        + """

@pytest.mark.usefixtures("tracker")
@pytest.fixture(name="renamed")
def _factory():
    return "value"
"""
    )
    pytester.makepyfile("def test_it(renamed): assert renamed == 'value'")

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert events(pytester) == ["tracker"]


def test_the_named_fixture_marks_reach_the_test(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.slow
        @pytest.fixture
        def underlying():
            return None


        @pytest.mark.usefixtures("underlying")
        @pytest.fixture
        def marked():
            return None
        """
    )
    pytester.makepyfile("def test_it(marked): pass")

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


def test_the_closest_definition_of_the_named_fixture_runs(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        RECORDING_CONFTEST
        + """

@pytest.mark.usefixtures("tracker")
@pytest.fixture
def needs_tracker():
    return None
"""
    )
    pytester.mkpydir("sub")
    pytester.makepyfile(
        **{
            "sub/conftest": """
                import pytest

                from conftest import record


                @pytest.fixture
                def tracker():
                    record("overridden tracker")
            """,
            "sub/test_sub": "def test_it(needs_tracker): pass",
        }
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    assert events(pytester) == ["overridden tracker"]
