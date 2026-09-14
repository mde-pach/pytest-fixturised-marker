"""Turn a ``usefixtures`` mark on a fixture into a real dependency of that fixture.

The names are appended to the fixture's argument names, which is how pytest already expresses
"set this up first", and the fixture function is wrapped so the extra values it never asked for are
dropped before it is called.
"""

from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Any, Callable

from _pytest import fixtures as _fixtures

from pytest_fixturised_marker._guard import marks_of

if TYPE_CHECKING:
    from collections.abc import Sequence

_ENABLED = False


def _requested_names(func: Any) -> tuple[str, ...]:
    names: list[str] = []
    for mark in marks_of(func):
        if mark.name == "usefixtures":
            names.extend(str(argument) for argument in mark.args)
    return tuple(names)


def _dropping(func: Callable[..., Any], extra: Sequence[str]) -> Callable[..., Any]:
    def without_extra(kwargs: dict[str, Any]) -> dict[str, Any]:
        return {name: value for name, value in kwargs.items() if name not in extra}

    if inspect.isasyncgenfunction(func):

        async def async_generator(*args: Any, **kwargs: Any) -> Any:
            async for value in func(*args, **without_extra(kwargs)):
                yield value

        return functools.wraps(func)(async_generator)

    if inspect.iscoroutinefunction(func):

        async def coroutine(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **without_extra(kwargs))

        return functools.wraps(func)(coroutine)

    if inspect.isgeneratorfunction(func):

        def generator(*args: Any, **kwargs: Any) -> Any:
            yield from func(*args, **without_extra(kwargs))

        return functools.wraps(func)(generator)

    def plain(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **without_extra(kwargs))

    return functools.wraps(func)(plain)


def _wire_requested_fixtures(original: Callable[..., None]) -> Callable[..., None]:
    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:  # noqa: N807
        original(self, *args, **kwargs)
        func = getattr(self, "func", None)
        if func is None:
            return
        extra = tuple(
            name
            for name in _requested_names(func)
            if name not in self.argnames and name != self.argname
        )
        if not extra:
            return
        self.func = _dropping(func, extra)
        self.argnames = (*self.argnames, *extra)

    return __init__


def enable() -> None:
    """Install the replacement once, before any fixture definition is collected."""
    global _ENABLED
    if _ENABLED:
        return
    _ENABLED = True
    fixtures: Any = _fixtures
    fixtures.FixtureDef.__init__ = _wire_requested_fixtures(_fixtures.FixtureDef.__init__)
