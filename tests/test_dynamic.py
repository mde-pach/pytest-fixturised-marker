import pytest

from pytest_fixturised_marker._dynamic import requested_names

LOOKUP = {"key": "second"}
NAMES = ("first", "second")
NUMBER = 3
PREFIX = "fir"


class Holder:
    name = "second"


class Request:
    def getfixturevalue(self, argname: object = None) -> None: ...


@pytest.mark.usefixtures("marked_fixtures")
@pytest.mark.parametrize(
    "body",
    [
        'request.getfixturevalue("heavy")',
        "request.getfixturevalue(NAME)",
        'request.getfixturevalue("hea" + "vy")',
        'request.getfixturevalue(f"hea{SUFFIX}")',
        "request.getfixturevalue(NAMES[0])",
        "request.getfixturevalue(LOOKUP['key'])",
        "request.getfixturevalue(Holder.name)",
        "local = NAME\n            request.getfixturevalue(local)",
        "for name in NAMES:\n                request.getfixturevalue(name)",
    ],
    ids=[
        "literal",
        "module constant",
        "concatenation",
        "f-string",
        "index",
        "dict lookup",
        "class attribute",
        "local variable",
        "loop target",
    ],
)
def test_the_name_is_resolved(pytester: pytest.Pytester, body: str) -> None:
    pytester.makepyfile(
        f"""
        NAME = "heavy"
        SUFFIX = "vy"
        NAMES = ("heavy",)
        LOOKUP = {{"key": "heavy"}}

        class Holder:
            name = "heavy"

        def test_it(request):
            {body}
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_a_fixture_asking_at_runtime_marks_the_test(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest


        @pytest.fixture
        def asks_at_runtime(request):
            return request.getfixturevalue("heavy")


        def test_it(asks_at_runtime): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_a_test_that_asks_for_nothing_is_left_alone(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_it(request):
            assert request is not None
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=0)


def test_repeated_names_are_reported_once() -> None:
    def sample(request: Request) -> None:
        request.getfixturevalue("first")
        request.getfixturevalue("second")
        request.getfixturevalue("first")

    assert requested_names(sample) == ("first", "second")


def test_a_closure_variable_is_resolved() -> None:
    chosen = "second"

    def sample(request: Request) -> None:
        request.getfixturevalue(chosen)

    assert requested_names(sample) == ("second",)


def test_every_branch_of_a_conditional_is_reported() -> None:
    def sample(request: Request, flag: bool) -> None:
        request.getfixturevalue("first" if flag else "second")

    assert requested_names(sample) == ("first", "second")


def test_a_name_produced_by_a_call_is_left_alone() -> None:
    def pick() -> str:
        return "first"

    def sample(request: Request) -> None:
        request.getfixturevalue(pick())

    assert requested_names(sample) == ()


def test_a_self_referencing_name_does_not_recurse() -> None:
    def sample(request: Request) -> None:
        name = "first"
        name = name + name
        request.getfixturevalue(name)

    assert requested_names(sample) == ("first",)


def test_a_builtin_without_source_is_handled() -> None:
    assert requested_names(len) == ()


@pytest.mark.usefixtures("marked_fixtures")
def test_the_keyword_form_is_recognised(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_it(request):
            assert request.getfixturevalue(argname="heavy") == "heavy"
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_any_receiver_name_is_recognised(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_it(request):
            handle = request
            assert handle.getfixturevalue("heavy") == "heavy"
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_a_call_inside_a_nested_function_is_recognised(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_it(request):
            def inner():
                return request.getfixturevalue("heavy")

            assert inner() == "heavy"
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


@pytest.mark.usefixtures("marked_fixtures")
def test_an_unknown_fixture_name_does_not_break_collection(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_it(request):
            request.getfixturevalue("nonexistent")
        """
    )

    result = pytester.runpytest()

    assert result.parseoutcomes().get("errors", 0) + result.parseoutcomes().get("failed", 0) == 1
    result.stdout.fnmatch_lines(["*nonexistent*"])


def test_a_call_inside_a_lambda_is_recognised() -> None:
    def sample(request: Request) -> None:
        (lambda: request.getfixturevalue("first"))()

    assert requested_names(sample) == ("first",)


def test_a_local_binding_shadows_a_module_constant() -> None:
    def sample(request: Request) -> None:
        name = "second"
        request.getfixturevalue(name)

    assert requested_names(sample) == ("second",)


@pytest.mark.usefixtures("marked_fixtures")
def test_an_undefined_name_leaves_the_test_unmarked(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_it(request):
            request.getfixturevalue(UNDEFINED)
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=0)


def test_a_value_that_is_not_a_string_is_ignored() -> None:
    def sample(request: Request) -> None:
        request.getfixturevalue(NUMBER)

    assert requested_names(sample) == ()


def test_a_call_with_no_argument_is_ignored() -> None:
    def sample(request: Request) -> None:
        request.getfixturevalue()

    assert requested_names(sample) == ()


def test_a_function_without_readable_source_is_handled() -> None:
    namespace: dict[str, object] = {}
    exec("def sample(request): request.getfixturevalue('first')", namespace)

    assert requested_names(namespace["sample"]) == ()
