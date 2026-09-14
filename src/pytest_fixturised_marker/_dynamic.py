"""Find the fixture names a test asks for at run time through ``request.getfixturevalue``.

The name is read off the source. A literal is taken as it is; a variable, attribute, concatenation,
f-string or loop target is resolved against the constants the module and the function already hold.
Nothing that could run user code is evaluated, so a name that only exists once the test is running
stays invisible.
"""

from __future__ import annotations

import ast
import inspect
import itertools
import textwrap
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from types import CodeType

_CALL_NAME = "getfixturevalue"
_ARGUMENT_NAME = "argname"
_MAX_CANDIDATES = 64
_CACHE: dict[CodeType, tuple[str, ...]] = {}


def requested_names(function: Any) -> tuple[str, ...]:
    """Return the fixture names `function` requests by name at run time."""
    code = getattr(function, "__code__", None)
    if code is None:
        return ()
    cached = _CACHE.get(code)
    if cached is None:
        cached = _scan(function)
        _CACHE[code] = cached
    return cached


def _scan(function: Any) -> tuple[str, ...]:
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    except (OSError, TypeError, SyntaxError, IndentationError):
        return ()
    scope = _Scope(function, tree)
    names: list[str] = []
    for node in ast.walk(tree):
        argument = _requested_argument(node)
        if argument is None:
            continue
        names.extend(value for value in scope.resolve(argument) if isinstance(value, str))
    return tuple(dict.fromkeys(names))


def _requested_argument(node: ast.AST) -> ast.expr | None:
    if not isinstance(node, ast.Call):
        return None
    called = node.func
    attribute = getattr(called, "attr", None) or getattr(called, "id", None)
    if attribute != _CALL_NAME:
        return None
    if node.args:
        return node.args[0]
    for keyword in node.keywords:
        if keyword.arg == _ARGUMENT_NAME:
            return keyword.value
    return None


class _Scope:
    """The constants a function's source can be read against, without executing any of it."""

    def __init__(self, function: Any, tree: ast.AST) -> None:
        self._outer = _outer_scope(function)
        self._assigned: dict[str, list[ast.expr]] = {}
        self._iterated: dict[str, list[ast.expr]] = {}
        self._resolving: set[str] = set()
        self._collect(tree)

    def _collect(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._assigned.setdefault(target.id, []).append(node.value)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                if isinstance(node.target, ast.Name) and node.value is not None:
                    self._assigned.setdefault(node.target.id, []).append(node.value)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)) and isinstance(
                node.target, ast.Name
            ):
                self._iterated.setdefault(node.target.id, []).append(node.iter)

    def resolve(self, node: ast.expr) -> tuple[Any, ...]:
        """Return every value `node` can hold, or nothing when it cannot be known statically."""
        return tuple(itertools.islice(self._resolve(node), _MAX_CANDIDATES))

    def _resolve(self, node: ast.expr) -> Iterator[Any]:
        if isinstance(node, ast.Constant):
            yield node.value
        elif isinstance(node, ast.Name):
            yield from self._resolve_name(node.id)
        elif isinstance(node, ast.Attribute):
            yield from self._resolve_attribute(node)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            yield from self._resolve_addition(node)
        elif isinstance(node, ast.JoinedStr):
            yield from self._resolve_joined(node)
        elif isinstance(node, ast.IfExp):
            yield from self._resolve(node.body)
            yield from self._resolve(node.orelse)
        elif isinstance(node, ast.Subscript):
            yield from self._resolve_subscript(node)
        elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            yield from self._resolve_sequence(node)

    def _resolve_name(self, name: str) -> Iterator[Any]:
        if name in self._resolving:
            return
        self._resolving.add(name)
        try:
            found = False
            for value_node in self._assigned.get(name, ()):
                found = True
                yield from self._resolve(value_node)
            for iterable_node in self._iterated.get(name, ()):
                found = True
                yield from self._elements(iterable_node)
            if not found and name in self._outer:
                yield self._outer[name]
        finally:
            self._resolving.discard(name)

    def _resolve_attribute(self, node: ast.Attribute) -> Iterator[Any]:
        for owner in self._resolve(node.value):
            if isinstance(owner, (str, bytes, int, float)):
                continue
            try:
                yield getattr(owner, node.attr)
            except Exception:
                continue

    def _resolve_addition(self, node: ast.BinOp) -> Iterator[Any]:
        for left, right in itertools.product(self._resolve(node.left), self._resolve(node.right)):
            if isinstance(left, str) and isinstance(right, str):
                yield left + right

    def _resolve_joined(self, node: ast.JoinedStr) -> Iterator[Any]:
        parts: list[tuple[str, ...]] = []
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                if value.format_spec is not None or value.conversion not in (-1, ord("s")):
                    return
                candidates = tuple(v for v in self._resolve(value.value) if isinstance(v, str))
            else:
                candidates = tuple(v for v in self._resolve(value) if isinstance(v, str))
            if not candidates:
                return
            parts.append(candidates)
        for combination in itertools.product(*parts):
            yield "".join(combination)

    def _resolve_subscript(self, node: ast.Subscript) -> Iterator[Any]:
        for container, index in itertools.product(
            self._resolve(node.value), self._resolve(node.slice)
        ):
            if isinstance(container, (list, tuple, dict)):
                try:
                    yield container[index]
                except (KeyError, IndexError, TypeError):
                    continue

    def _resolve_sequence(self, node: ast.Tuple | ast.List | ast.Set) -> Iterator[Any]:
        resolved: list[Any] = []
        for element in node.elts:
            candidates = self.resolve(element)
            if len(candidates) != 1:
                return
            resolved.append(candidates[0])
        yield tuple(resolved)

    def _elements(self, node: ast.expr) -> Iterator[Any]:
        for container in self._resolve(node):
            if isinstance(container, (str, bytes)):
                continue
            yield from _safe_iter(container)


def _safe_iter(container: Any) -> Iterable[Any]:
    if isinstance(container, (list, tuple, set, frozenset)):
        return container
    if isinstance(container, dict):
        return container.keys()
    return ()


def _outer_scope(function: Any) -> dict[str, Any]:
    scope: dict[str, Any] = dict(getattr(function, "__globals__", None) or {})
    code = getattr(function, "__code__", None)
    closure = getattr(function, "__closure__", None)
    if code is not None and closure:
        names: Sequence[str] = getattr(code, "co_freevars", ())
        for name, cell in zip(names, closure):
            try:
                scope[name] = cell.cell_contents
            except ValueError:
                continue
    return scope
