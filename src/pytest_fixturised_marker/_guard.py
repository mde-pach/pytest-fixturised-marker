"""Let pytest store marks on fixture functions instead of refusing them.

pytest rejects ``@pytest.mark.x`` on a fixture in two places: when the mark is applied to an
existing fixture, and when ``@pytest.fixture`` is applied to an already marked function. Both are
replaced here so that the mark always lands on the function a ``FixtureDef`` exposes.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable

from _pytest import fixtures as _fixtures
from _pytest.mark import structures as _structures

if TYPE_CHECKING:
    from _pytest.mark.structures import Mark

_ENABLED = False


def underlying_function(obj: Any) -> Any:
    """Return the plain function behind a fixture object, whatever pytest wrapped it in."""
    fixture_function = getattr(obj, "_fixture_function", None)
    if fixture_function is not None:
        return fixture_function
    return inspect.unwrap(obj)


def marks_of(obj: Any) -> list[Mark]:
    """Return the marks carried by a fixture function."""
    return list(getattr(underlying_function(obj), "pytestmark", []))


def _is_fixture(obj: Any) -> bool:
    return _fixtures.getfixturemarker(obj) is not None


def _store_mark_on_fixtures(original: Callable[..., None]) -> Callable[..., None]:
    def store_mark(obj: Any, mark: Mark, *args: Any, **kwargs: Any) -> None:
        if not _is_fixture(obj):
            original(obj, mark, *args, **kwargs)
            return
        target = underlying_function(obj)
        target.pytestmark = [*getattr(target, "pytestmark", []), mark]

    return store_mark


def _keep_marks_through_fixture(original: Callable[..., Any]) -> Callable[..., Any]:
    def __call__(self: Any, function: Any) -> Any:  # noqa: N807
        marks = vars(function).pop("pytestmark", None) if hasattr(function, "__dict__") else None
        result = original(self, function)
        if marks is not None:
            function.pytestmark = marks
        return result

    return __call__


def enable() -> None:
    """Install the replacements once, before any conftest or test module is imported."""
    global _ENABLED
    if _ENABLED:
        return
    _ENABLED = True
    structures: Any = _structures
    fixtures: Any = _fixtures
    structures.store_mark = _store_mark_on_fixtures(_structures.store_mark)
    fixtures.FixtureFunctionMarker.__call__ = _keep_marks_through_fixture(
        _fixtures.FixtureFunctionMarker.__call__
    )
