import pytest

PARAMETRISING_CONFTEST = """
import pytest


@pytest.mark.parametrize("value", [1, 2])
@pytest.fixture
def parametrising():
    return "parametrising"


@pytest.fixture
def wraps_parametrising(parametrising):
    return parametrising
"""


@pytest.fixture
def parametrising_fixtures(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(PARAMETRISING_CONFTEST)


@pytest.mark.usefixtures("parametrising_fixtures")
def test_users_are_parametrised(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(parametrising, value): assert value in (1, 2)")

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


@pytest.mark.usefixtures("parametrising_fixtures")
def test_transitive_users_are_parametrised(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(wraps_parametrising, value): assert value in (1, 2)")

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


@pytest.mark.usefixtures("parametrising_fixtures")
def test_it_multiplies_with_the_test_own_parametrization(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize("letter", ["a", "b"])
        def test_it(parametrising, value, letter): pass
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=4)


@pytest.mark.usefixtures("parametrising_fixtures")
def test_unrelated_tests_are_not_parametrised(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_it(): pass")

    result = pytester.runpytest("--collect-only", "-q")

    assert "test_it[" not in result.stdout.str()


def test_parameter_identifiers_and_marks_survive(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.parametrize(
            "value",
            [pytest.param(1, id="one"), pytest.param(2, id="two", marks=pytest.mark.slow)],
        )
        @pytest.fixture
        def parametrising():
            return None
        """
    )
    pytester.makepyfile("def test_it(parametrising, value): pass")

    result = pytester.runpytest("-m", "not slow", "-v")

    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*test_it[[]one[]]*"])


def test_the_fixture_can_consume_its_own_parameter(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.parametrize("backend", ["memory", "disk"])
        @pytest.fixture
        def store(backend):
            return f"store on {backend}"
        """
    )
    pytester.makepyfile(
        """
        def test_it(store):
            assert store in ("store on memory", "store on disk")
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


def test_the_same_parametrization_is_applied_once(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.parametrize("value", [1, 2])
        @pytest.fixture
        def first():
            return None


        @pytest.mark.parametrize("value", [1, 2])
        @pytest.fixture
        def second():
            return None
        """
    )
    pytester.makepyfile("def test_it(first, second, value): pass")

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


def test_a_test_that_ignores_the_parameter_is_reported(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.parametrize("value", [1, 2])
        @pytest.fixture
        def parametrising():
            return None
        """
    )
    pytester.makepyfile("def test_it(parametrising): pass")

    result = pytester.runpytest()

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*uses no argument 'value'*"])


def test_indirect_parametrization_reaches_the_named_fixture(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.fixture
        def backend(request):
            return f"backend {request.param}"


        @pytest.mark.parametrize("backend", ["memory", "disk"], indirect=True)
        @pytest.fixture
        def store(backend):
            return backend
        """
    )
    pytester.makepyfile(
        """
        def test_it(store):
            assert store in ("backend memory", "backend disk")
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)


def test_identifier_callables_are_used(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.parametrize("value", [1, 2], ids=lambda value: f"n{value}")
        @pytest.fixture
        def parametrising():
            return None
        """
    )
    pytester.makepyfile("def test_it(parametrising, value): pass")

    result = pytester.runpytest("-v")

    result.assert_outcomes(passed=2)
    result.stdout.fnmatch_lines(["*test_it[[]n1[]]*", "*test_it[[]n2[]]*"])


def test_two_fixtures_multiply_their_parameters(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.parametrize("first", [1, 2])
        @pytest.fixture
        def one():
            return None


        @pytest.mark.parametrize("second", ["a", "b"])
        @pytest.fixture
        def two():
            return None
        """
    )
    pytester.makepyfile("def test_it(one, two, first, second): pass")

    result = pytester.runpytest()

    result.assert_outcomes(passed=4)


def test_an_autouse_fixture_parametrizes_every_test_in_scope(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.parametrize("value", [1, 2])
        @pytest.fixture(autouse=True)
        def always():
            return None
        """
    )
    pytester.makepyfile(
        """
        def test_one(value): pass
        def test_two(value): pass
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=4)


def test_a_replacing_override_drops_the_parametrization(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.parametrize("value", [1, 2])
        @pytest.fixture
        def parametrising():
            return None
        """
    )
    pytester.mkpydir("sub")
    pytester.makepyfile(
        **{
            "sub/conftest": """
                import pytest

                @pytest.fixture
                def parametrising():
                    return None
            """,
            "sub/test_sub": "def test_it(parametrising): pass",
        }
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)


def test_a_conflict_with_the_test_own_parametrization_is_reported(
    pytester: pytest.Pytester,
) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.parametrize("value", [1, 2])
        @pytest.fixture
        def parametrising():
            return None
        """
    )
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize("value", [3])
        def test_it(parametrising, value): pass
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*duplicate*value*"])


def test_a_marked_fixture_can_also_parametrize(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest


        @pytest.mark.slow
        @pytest.mark.parametrize("value", [1, 2])
        @pytest.fixture
        def both():
            return None
        """
    )
    pytester.makepyfile("def test_it(both, value): pass")

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=2)
