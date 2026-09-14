"""Plain pytest behaviour, unchanged by the three internals this plugin replaces."""

import pytest

from _outcomes import deselected


def test_a_mark_on_a_test_still_selects(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.slow
        def test_marked(): pass

        def test_plain(): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)
    assert deselected(result) == 1


def test_a_mark_on_a_class_still_reaches_its_methods(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.slow
        class TestThings:
            def test_one(self): pass
            def test_two(self): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=2)


def test_a_module_level_pytestmark_still_applies(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        pytestmark = pytest.mark.slow

        def test_one(): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


def test_a_list_of_module_level_marks_still_applies(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        pytestmark = [pytest.mark.slow, pytest.mark.network]

        def test_one(): pass
        """
    )

    result = pytester.runpytest("-m", "slow and network")

    result.assert_outcomes(passed=1)


def test_marks_are_still_inherited_through_a_class_hierarchy(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.slow
        class Base:
            def test_inherited(self): pass

        class TestChild(Base):
            pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.parametrize(
    ("mark", "outcomes"),
    [
        ("skip", {"skipped": 1}),
        ("skipif(True, reason='no')", {"skipped": 1}),
        ("skipif(False, reason='no')", {"passed": 1}),
        ("xfail(reason='known')", {"xpassed": 1}),
        ("xfail(reason='known', strict=True)", {"failed": 1}),
    ],
)
def test_conditional_marks_on_tests_are_unchanged(
    pytester: pytest.Pytester, mark: str, outcomes: dict[str, int]
) -> None:
    pytester.makepyfile(
        f"""
        import pytest

        @pytest.mark.{mark}
        def test_it(): pass
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(**outcomes)


def test_parametrize_on_a_test_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize("value", [1, 2, 3])
        def test_it(value): assert value
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=3)


def test_marks_inside_parametrize_are_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize(
            "value", [1, pytest.param(2, marks=pytest.mark.skip(reason="nope"))]
        )
        def test_it(value): pass
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1, skipped=1)


def test_usefixtures_on_a_test_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pathlib

        import pytest


        @pytest.fixture
        def touches():
            pathlib.Path("touched").touch()
        """
    )
    pytester.makepyfile(
        """
        import pathlib

        import pytest

        @pytest.mark.usefixtures("touches")
        def test_it(): assert pathlib.Path("touched").exists()
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_usefixtures_on_a_class_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pathlib

        import pytest


        @pytest.fixture
        def touches():
            pathlib.Path("touched").touch()
        """
    )
    pytester.makepyfile(
        """
        import pathlib

        import pytest

        @pytest.mark.usefixtures("touches")
        class TestThings:
            def test_it(self): assert pathlib.Path("touched").exists()
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_keyword_selection_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_wanted(): pass
        def test_other(): pass
        """
    )

    result = pytester.runpytest("-k", "wanted")

    result.assert_outcomes(passed=1)
    assert deselected(result) == 1


def test_strict_markers_still_rejects_an_unknown_mark_on_a_test(
    pytester: pytest.Pytester,
) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.unregistered
        def test_it(): pass
        """
    )

    result = pytester.runpytest("--strict-markers")

    result.stdout.fnmatch_lines(["*'unregistered' not found in `markers` configuration option*"])


def test_strict_markers_also_rejects_an_unknown_mark_on_a_fixture(
    pytester: pytest.Pytester,
) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.unregistered
        @pytest.fixture
        def marked():
            return None
        """
    )
    pytester.makepyfile("def test_it(marked): pass")

    result = pytester.runpytest_subprocess("--strict-markers")

    result.stdout.fnmatch_lines(["*'unregistered' not found in `markers` configuration option*"])


def test_a_yield_fixture_still_runs_in_order(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        events = []

        @pytest.fixture
        def resource():
            events.append("setup")
            yield "value"
            events.append("teardown")

        def test_one(resource):
            assert resource == "value"
            assert events == ["setup"]

        def test_two():
            assert events == ["setup", "teardown"]
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


def test_a_finalizer_still_runs(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        events = []

        @pytest.fixture
        def resource(request):
            request.addfinalizer(lambda: events.append("finalized"))
            return "value"

        def test_one(resource): pass

        def test_two(): assert events == ["finalized"]
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


def test_a_parametrized_fixture_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture(params=[1, 2], ids=["one", "two"])
        def value(request):
            return request.param

        def test_it(value): assert value in (1, 2)
        """
    )

    result = pytester.runpytest("-v")

    result.assert_outcomes(passed=2)
    result.stdout.fnmatch_lines(["*test_it[[]one[]]*", "*test_it[[]two[]]*"])


def test_an_autouse_fixture_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        events = []

        @pytest.fixture(autouse=True)
        def always():
            events.append("ran")

        def test_one(): assert events == ["ran"]
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_a_session_scoped_fixture_is_built_once(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest

        calls = []

        @pytest.fixture(scope="session")
        def once():
            calls.append(1)
            return len(calls)
        """
    )
    pytester.makepyfile(
        """
        def test_one(once): assert once == 1
        def test_two(once): assert once == 1
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


def test_an_unmarked_override_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def resource():
            return "base"
        """
    )
    pytester.mkpydir("sub")
    pytester.makepyfile(
        **{
            "sub/conftest": """
                import pytest

                @pytest.fixture
                def resource(resource):
                    return resource + " + sub"
            """,
            "sub/test_sub": "def test_it(resource): assert resource == 'base + sub'",
            "test_top": "def test_it(resource): assert resource == 'base'",
        }
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


def test_a_renamed_fixture_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture(name="renamed")
        def _factory():
            return "value"

        def test_it(renamed): assert renamed == "value"
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_a_unittest_test_case_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import unittest

        class TestThings(unittest.TestCase):
            def test_it(self):
                self.assertTrue(True)
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_a_failing_fixture_is_still_an_error(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def broken():
            raise RuntimeError("boom")

        def test_it(broken): pass
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*RuntimeError: boom*"])


def test_calling_a_fixture_directly_is_still_refused(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def resource():
            return "value"

        def test_it(): resource()
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*called directly*"])


def test_the_test_own_mark_stays_the_closest_one(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.slow("from the fixture")
        @pytest.fixture
        def marked():
            return None
        """
    )
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.slow("from the test")
        def test_it(marked, request):
            assert request.node.get_closest_marker("slow").args == ("from the test",)
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_without_the_plugin_a_fixture_mark_does_not_reach_the_test(
    pytester: pytest.Pytester,
) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.slow
        @pytest.fixture
        def marked():
            return None

        def test_it(marked): pass
        """
    )

    with_plugin = pytester.runpytest_subprocess("-m", "slow")
    without_plugin = pytester.runpytest_subprocess("-p", "no:fixturised_marker", "-m", "slow")

    with_plugin.assert_outcomes(passed=1)
    assert without_plugin.parseoutcomes().get("passed", 0) == 0


def test_doctest_collection_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        '''
        def add(first, second):
            """
            >>> add(1, 2)
            3
            """
            return first + second
        '''
    )

    result = pytester.runpytest("--doctest-modules")

    result.assert_outcomes(passed=1)


def test_an_empty_suite_is_unchanged(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def not_a_test(): pass")

    result = pytester.runpytest()

    result.assert_outcomes()
