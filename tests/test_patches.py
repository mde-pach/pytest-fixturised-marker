"""The pytest internals the plugin replaces are wrapped exactly once."""

from _pytest import fixtures as _fixtures
from _pytest.mark import structures as _structures

from pytest_fixturised_marker import _dependencies, _guard


def test_enabling_the_guard_again_changes_nothing() -> None:
    before = (_structures.store_mark, _fixtures.FixtureFunctionMarker.__call__)

    _guard.enable()

    assert (_structures.store_mark, _fixtures.FixtureFunctionMarker.__call__) == before


def test_enabling_the_dependency_wiring_again_changes_nothing() -> None:
    before = _fixtures.FixtureDef.__init__

    _dependencies.enable()

    assert _fixtures.FixtureDef.__init__ is before
