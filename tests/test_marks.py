"""A mark on a fixture reaching the tests that use it."""

import pytest

from _outcomes import deselected


@pytest.mark.usefixtures("marked_fixtures")
@pytest.mark.parametrize("fixture_name", ["heavy", "also_heavy"])
def test_either_decorator_order_marks_the_test(
    pytester: pytest.Pytester, fixture_name: str
) -> None:
    pytester.makepyfile(f"def test_it({fixture_name}): pass")

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_transitive_user_inherits_the_mark(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(wraps_heavy): pass")

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_a_long_chain_still_carries_the_mark(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def second(wraps_heavy): return wraps_heavy

        @pytest.fixture
        def third(second): return second

        def test_it(third): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_two_paths_to_the_same_fixture_mark_once(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def left(heavy): return heavy

        @pytest.fixture
        def right(heavy): return heavy

        def test_it(left, right, request):
            assert len(list(request.node.iter_markers("slow"))) == 1
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_usefixtures_on_the_test_inherits_the_mark(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.usefixtures("heavy")
        def test_it(): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_usefixtures_on_the_class_inherits_the_mark(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.usefixtures("heavy")
        class TestThings:
            def test_one(self): pass
            def test_two(self): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=2)


@pytest.mark.usefixtures("marked_fixtures")
def test_tests_in_a_class_inherit_the_mark(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        class TestThings:
            def test_it(self, heavy): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


def test_a_fixture_defined_in_the_test_module_marks_its_tests(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest


        @pytest.mark.slow
        @pytest.fixture
        def local():
            return None


        def test_marked(local): pass
        def test_plain(): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)
    assert deselected(result) == 1


def test_a_fixture_defined_in_a_class_marks_its_tests(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest


        class TestThings:
            @pytest.mark.slow
            @pytest.fixture
            def local(self):
                return None

            def test_it(self, local): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


def test_a_renamed_fixture_marks_its_tests(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.slow
        @pytest.fixture(name="renamed")
        def _factory():
            return "value"
        """
    )
    pytester.makepyfile("def test_it(renamed): assert renamed == 'value'")

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


def test_a_parametrized_fixture_can_also_carry_a_mark(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.slow
        @pytest.fixture(params=[1, 2])
        def value(request):
            return request.param
        """
    )
    pytester.makepyfile("def test_it(value): assert value in (1, 2)")

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=2)


def test_an_autouse_fixture_marks_only_its_own_directory(pytester: pytest.Pytester) -> None:
    pytester.mkpydir("sub")
    pytester.makepyfile(
        **{
            "sub/conftest": """
                import pytest


                @pytest.mark.slow
                @pytest.fixture(autouse=True)
                def always():
                    return None
            """,
            "sub/test_sub": "def test_sub(): pass",
            "test_top": "def test_top(): pass",
        }
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)
    assert deselected(result) == 1


@pytest.mark.usefixtures("marked_fixtures")
def test_skip_mark_skips_the_test_with_its_reason(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(needs_docker): pass")

    result = pytester.runpytest("-rs")

    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*no docker here*"])


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
def test_conditional_marks_are_evaluated(
    pytester: pytest.Pytester, mark: str, outcomes: dict[str, int]
) -> None:
    pytester.makeconftest(
        f"""
        import pytest


        @pytest.mark.{mark}
        @pytest.fixture
        def marked():
            return None
        """
    )
    pytester.makepyfile("def test_it(marked): pass")

    result = pytester.runpytest()

    result.assert_outcomes(**outcomes)


def test_filterwarnings_from_a_fixture_is_applied(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.filterwarnings("error")
        @pytest.fixture
        def strict():
            return None
        """
    )
    pytester.makepyfile(
        """
        import warnings

        import pytest

        def test_it(strict):
            with pytest.raises(UserWarning):
                warnings.warn("boom", UserWarning)
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_mark_arguments_survive(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.slow("very", level=3)
        @pytest.fixture
        def heavy():
            return None
        """
    )
    pytester.makepyfile(
        """
        def test_it(heavy, request):
            mark = request.node.get_closest_marker("slow")
            assert mark.args == ("very",)
            assert mark.kwargs == {"level": 3}
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_unhashable_mark_arguments_are_handled(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.slow(options={"depth": 2})
        @pytest.fixture
        def heavy():
            return None
        """
    )
    pytester.makepyfile(
        """
        def test_it(heavy, request):
            assert request.node.get_closest_marker("slow").kwargs == {"options": {"depth": 2}}
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_the_same_mark_with_different_arguments_is_kept_twice(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.slow("first")
        @pytest.fixture
        def one():
            return None


        @pytest.mark.slow("second")
        @pytest.fixture
        def two():
            return None
        """
    )
    pytester.makepyfile(
        """
        def test_it(one, two, request):
            assert len(list(request.node.iter_markers("slow"))) == 2
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_several_marks_on_one_fixture_all_apply(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.slow
        @pytest.mark.network
        @pytest.fixture
        def remote():
            return None
        """
    )
    pytester.makepyfile("def test_it(remote): pass")

    for expression in ("slow", "network", "slow and network"):
        result = pytester.runpytest("-m", expression)
        result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_the_same_mark_is_applied_once(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_it(heavy, also_heavy, request):
            assert len(list(request.node.iter_markers("slow"))) == 1
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_a_mark_already_on_the_test_is_not_duplicated(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.slow
        def test_it(heavy, request):
            assert len(list(request.node.iter_markers("slow"))) == 1
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_a_mark_inherited_from_the_module_is_not_duplicated(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        pytestmark = pytest.mark.slow

        def test_it(heavy, request):
            assert len(list(request.node.iter_markers("slow"))) == 1
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_the_propagated_mark_is_selectable_by_keyword(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_one(heavy): pass
        def test_two(): pass
        """
    )

    result = pytester.runpytest("-k", "slow")

    result.assert_outcomes(passed=1)
    assert deselected(result) == 1


@pytest.mark.usefixtures("marked_fixtures")
def test_unrelated_test_is_left_alone(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(): pass")

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=0)
    assert deselected(result) == 1


@pytest.mark.usefixtures("marked_fixtures")
def test_marked_and_unmarked_tests_are_split(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_slow(heavy): pass
        def test_fast(): pass
        """
    )

    result = pytester.runpytest("-m", "not slow")

    result.assert_outcomes(passed=1)
    assert deselected(result) == 1


@pytest.mark.usefixtures("marked_fixtures")
def test_test_identifiers_are_untouched(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(heavy): pass")

    result = pytester.runpytest("--collect-only", "-q")

    result.stdout.fnmatch_lines(["*::test_it"])
    assert "test_it[" not in result.stdout.str()


@pytest.mark.usefixtures("marked_fixtures")
def test_existing_parametrization_is_preserved(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize("value", [1, 2])
        def test_it(heavy, value): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=2)


def test_a_fixture_without_marks_changes_nothing(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def plain():
            return "value"
        """
    )
    pytester.makepyfile(
        """
        def test_it(plain, request):
            assert plain == "value"
            assert list(request.node.own_markers) == []
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_a_mark_inherited_from_the_class_is_not_duplicated(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.slow
        class TestThings:
            def test_it(self, heavy, request):
                assert len(list(request.node.iter_markers("slow"))) == 1
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


@pytest.mark.parametrize("scope", ["function", "class", "module", "package", "session"])
def test_a_mark_survives_every_fixture_scope(pytester: pytest.Pytester, scope: str) -> None:
    pytester.makeconftest(
        f"""
        import pytest


        @pytest.mark.slow
        @pytest.fixture(scope="{scope}")
        def scoped():
            return None
        """
    )
    pytester.makepyfile("def test_it(scoped): pass")

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


def test_a_fixture_from_a_registered_plugin_marks_its_tests(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        marking_plugin="""
        import pytest


        @pytest.mark.slow
        @pytest.fixture
        def from_plugin():
            return "value"
        """
    )
    pytester.makeconftest('pytest_plugins = ["marking_plugin"]')
    pytester.makepyfile("def test_it(from_plugin): assert from_plugin == 'value'")

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_an_autouse_fixture_can_carry_the_mark_in(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest


        @pytest.fixture(autouse=True)
        def pulls_it_in(heavy):
            return heavy


        def test_it(): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)
