"""Which definition of an overridden fixture a mark follows."""

import pytest

from _outcomes import deselected

MARKED_BASE = """
import pytest


@pytest.mark.slow
@pytest.fixture
def resource():
    return "base"
"""


def test_a_replacing_override_drops_the_mark(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(MARKED_BASE)
    pytester.mkpydir("sub")
    pytester.makepyfile(
        **{
            "sub/conftest": """
                import pytest

                @pytest.fixture
                def resource():
                    return "replacement"
            """,
            "sub/test_sub": "def test_it(resource): assert resource == 'replacement'",
        }
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=0)
    assert deselected(result) == 1


def test_an_extending_override_keeps_the_mark(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(MARKED_BASE)
    pytester.mkpydir("sub")
    pytester.makepyfile(
        **{
            "sub/conftest": """
                import pytest

                @pytest.fixture
                def resource(resource):
                    return resource + " + extended"
            """,
            "sub/test_sub": "def test_it(resource): assert resource == 'base + extended'",
        }
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


def test_a_marked_override_applies_to_its_own_scope_only(pytester: pytest.Pytester) -> None:
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


                @pytest.mark.slow
                @pytest.fixture
                def resource():
                    return "marked override"
            """,
            "sub/test_sub": "def test_sub(resource): pass",
            "test_top": "def test_top(resource): pass",
        }
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)
    assert deselected(result) == 1


def test_an_override_in_the_test_module_replaces_the_mark(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(MARKED_BASE)
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def resource():
            return "module"

        def test_it(resource): assert resource == "module"
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=0)
    assert deselected(result) == 1


def test_an_override_in_the_test_module_can_extend(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(MARKED_BASE)
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def resource(resource):
            return resource + " + module"

        def test_it(resource): assert resource == "base + module"
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)


def test_an_override_in_a_class_replaces_the_mark(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(MARKED_BASE)
    pytester.makepyfile(
        """
        import pytest

        class TestThings:
            @pytest.fixture
            def resource(self):
                return "class"

            def test_it(self, resource): assert resource == "class"
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=0)
    assert deselected(result) == 1


def test_a_marked_override_in_a_class_marks_its_tests(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def resource():
            return "base"
        """
    )
    pytester.makepyfile(
        """
        import pytest

        class TestThings:
            @pytest.mark.slow
            @pytest.fixture
            def resource(self):
                return "class"

            def test_it(self, resource): pass

        def test_outside(resource): pass
        """
    )

    result = pytester.runpytest("-m", "slow")

    result.assert_outcomes(passed=1)
    assert deselected(result) == 1


def test_a_chain_of_overrides_follows_each_link(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(MARKED_BASE)
    pytester.mkpydir("sub")
    pytester.mkpydir("sub/deep")
    pytester.makepyfile(
        **{
            "sub/conftest": """
                import pytest

                @pytest.fixture
                def resource(resource):
                    return resource + " + sub"
            """,
            "sub/deep/conftest": """
                import pytest

                @pytest.fixture
                def resource():
                    return "deep"
            """,
            "test_top": "def test_top(resource): pass",
            "sub/test_sub": "def test_sub(resource): pass",
            "sub/deep/test_deep": "def test_deep(resource): pass",
        }
    )

    result = pytester.runpytest("-m", "slow", "-v")

    result.assert_outcomes(passed=2)
    assert deselected(result) == 1
    output = result.stdout.str()
    assert "test_top" in output
    assert "test_sub" in output
    assert "test_deep" not in output


def test_both_definitions_contribute_their_marks_when_extended(
    pytester: pytest.Pytester,
) -> None:
    pytester.makeconftest(MARKED_BASE)
    pytester.mkpydir("sub")
    pytester.makepyfile(
        **{
            "sub/conftest": """
                import pytest


                @pytest.mark.network
                @pytest.fixture
                def resource(resource):
                    return resource + " + sub"
            """,
            "sub/test_sub": "def test_it(resource): pass",
        }
    )

    result = pytester.runpytest("-m", "slow and network")

    result.assert_outcomes(passed=1)


def test_a_replacing_override_contributes_only_its_own_mark(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(MARKED_BASE)
    pytester.mkpydir("sub")
    pytester.makepyfile(
        **{
            "sub/conftest": """
                import pytest


                @pytest.mark.network
                @pytest.fixture
                def resource():
                    return "replacement"
            """,
            "sub/test_sub": "def test_it(resource): pass",
        }
    )

    result = pytester.runpytest("-m", "network and not slow")

    result.assert_outcomes(passed=1)
