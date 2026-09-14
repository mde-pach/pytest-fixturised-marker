"""Propagate pytest marks from fixtures to the tests that use them."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, Protocol, cast

import pytest
from _pytest import fixtures as _fixtures

from pytest_fixturised_marker import _dependencies, _dynamic, _guard

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from _pytest.mark.structures import Mark

_guard.enable()
_dependencies.enable()

PARAMETRIZE = "parametrize"
USEFIXTURES = "usefixtures"

_GETFIXTUREDEFS_TAKES_NODE = (
    "node" in inspect.signature(_fixtures.FixtureManager.getfixturedefs).parameters
)


class _FixtureDef(Protocol):
    @property
    def argnames(self) -> tuple[str, ...]: ...

    @property
    def func(self) -> Callable[..., Any]: ...


def _as_decorator(mark: Mark) -> pytest.MarkDecorator:
    decorator: pytest.MarkDecorator = getattr(pytest.mark, mark.name)
    return decorator.with_args(*mark.args, **mark.kwargs)


def _active(fixturedefs: Sequence[_FixtureDef], name: str) -> Iterator[_FixtureDef]:
    """Yield the definitions of `name` that actually run, closest override first."""
    for index in reversed(range(len(fixturedefs))):
        fixturedef = fixturedefs[index]
        yield fixturedef
        if name not in fixturedef.argnames:
            return


def _marks(fixturedefs: Sequence[_FixtureDef], name: str) -> Iterator[Mark]:
    for fixturedef in _active(fixturedefs, name):
        yield from _guard.marks_of(fixturedef.func)


def _declared_marks(
    name2fixturedefs: Mapping[str, Sequence[_FixtureDef]], names: Sequence[str]
) -> Iterator[Mark]:
    for name in names:
        yield from _marks(name2fixturedefs.get(name) or (), name)


def _known_elsewhere(item: pytest.Item, name: str) -> Sequence[_FixtureDef]:
    """Look up a fixture the test never declared, so it is absent from its closure."""
    manager = getattr(item.session, "_fixturemanager", None)
    if manager is None:
        return ()
    target = item if _GETFIXTUREDEFS_TAKES_NODE else item.nodeid
    return cast("Sequence[_FixtureDef]", manager.getfixturedefs(name, target) or ())


def _marks_of(item: pytest.Item) -> Iterator[Mark]:
    fixtureinfo = getattr(item, "_fixtureinfo", None)
    name2fixturedefs: Mapping[str, Sequence[_FixtureDef]] = (
        cast("Mapping[str, Sequence[_FixtureDef]]", fixtureinfo.name2fixturedefs)
        if fixtureinfo is not None
        else {}
    )
    pending = [
        *getattr(item, "fixturenames", ()),
        *_dynamic.requested_names(getattr(item, "function", None)),
    ]
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        for fixturedef in _active(name2fixturedefs.get(name) or _known_elsewhere(item, name), name):
            yield from _guard.marks_of(fixturedef.func)
            pending.extend(_dynamic.requested_names(_guard.underlying_function(fixturedef.func)))


@pytest.hookimpl(tryfirst=True)
def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    name2fixturedefs = cast("Mapping[str, Sequence[_FixtureDef]]", metafunc._arg2fixturedefs)
    applied: list[Mark] = []
    for mark in _declared_marks(name2fixturedefs, metafunc.fixturenames):
        if mark.name != PARAMETRIZE or mark in applied:
            continue
        applied.append(mark)
        metafunc.parametrize(*mark.args, **mark.kwargs)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        applied = list(item.iter_markers())
        for mark in _marks_of(item):
            if mark.name in (PARAMETRIZE, USEFIXTURES) or mark in applied:
                continue
            applied.append(mark)
            item.add_marker(_as_decorator(mark))
