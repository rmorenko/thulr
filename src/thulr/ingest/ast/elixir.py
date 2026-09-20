"""Elixir policy: every definition is a macro call, told apart by its keyword.

The other languages here hand tree-sitter a node type and get a
definition back — `function_declaration`, `method`, `class`. Elixir has
none. `defmodule`, `def`, `defp` and `defmacro` are macros, so the
grammar reports all of them as `call`, and which one it is lives in the
text of the call's first child. `NestedPolicy` keys off node types and
therefore cannot express this at all, which is why this file is written
by hand rather than declared as four tuples.

`@doc` and `@spec` are pulled into the span below them, on Elixir's own
rule rather than one invented here: an attribute documents the
definition it precedes, and a blank line detaches it. Left alone,
`@doc "Fetches the value, or nil when the key has expired"` becomes a
chunk of its own — the most searchable sentence about a function, filed
apart from the function. `@moduledoc` is deliberately not attached: it
describes the module, not whichever `def` happens to follow it.

Why this language and not another: 50 of the 204 harvested acceptance
questions were unreachable, every one of them Elixir, because no grammar
covered it. They were not ranked badly — no chunk covered the answer at
all, so no retrieval change could ever have moved them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from thulr.ingest.ast.core import Span, line_span, mark_covered

if TYPE_CHECKING:
    from tree_sitter import Node

_MAX_NESTING = 8
"""How deep module recursion goes. Elixir nests two or three levels in
practice; a bound keeps a damaged tree from costing a run."""

_DEFINITIONS = (
    "def",
    "defp",
    "defmacro",
    "defmacrop",
    "defguard",
    "defguardp",
    "defdelegate",
)
"""Macros that introduce something callable. Public and private both:
`defp` is where half of a module's real work lives, and a search that
skips it answers "where is this done" with the wrapper."""

_CONTAINERS = ("defmodule", "defprotocol", "defimpl")
"""Macros that hold definitions. Claimed the way a class is — not as one
chunk, but recursed into, so each function inside gets its own and the
module's own lines fall through to the gap pass."""

_ATTACHED = ("doc", "spec", "impl", "deprecated", "typedoc", "type", "opaque")
"""Attributes that belong to the definition beneath them. `moduledoc` is
absent on purpose: it documents the module."""


def _keyword(node: Node) -> str | None:
    """Which macro a `call` is, or None if it is an ordinary call."""
    if node.type != "call" or not node.named_children:
        return None
    first = node.named_children[0]
    if first.type != "identifier" or first.text is None:
        return None
    return first.text.decode()


def _name(node: Node) -> str | None:
    """The name a definition introduces.

    Four shapes reach here and all four are normal Elixir:
    `defmodule Pow.Store` (an `alias`), `def get(config, key)` (a `call`
    whose own first child is the name), `def get` with no parentheses (a
    bare `identifier`), and `defguard is_even(n) when ...` (a binary
    operator wrapping the call). The last is unwrapped by descending
    until something nameable appears.
    """
    arguments = next((c for c in node.named_children if c.type == "arguments"), None)
    if arguments is None or not arguments.named_children:
        return None
    target: Node | None = arguments.named_children[0]
    for _ in range(_MAX_NESTING):
        if target is None or target.text is None:
            return None
        if target.type in ("alias", "identifier"):
            return target.text.decode()
        if target.type == "call" and target.named_children:
            target = target.named_children[0]
            continue
        if target.named_children:  # `when` guards and other operators
            target = target.named_children[0]
            continue
        return None
    return None


def _extend_back(siblings: list[Node], *, index: int, start_line: int) -> int:
    """Pull `@doc`, `@spec` and `#` comments into the span below them.

    A blank line ends the chain, which is Elixir's own rule: an attribute
    separated from the definition below it documents nothing in
    particular, and `ExDoc` treats it that way too.
    """
    for previous in reversed(siblings[:index]):
        if previous.type == "comment":
            pass
        elif previous.type == "unary_operator":
            inner = _keyword(previous.named_children[0]) if previous.named_children else None
            if inner not in _ATTACHED:
                break
        else:
            break
        previous_start, previous_end = line_span(previous)
        if previous_end < start_line - 1:
            break  # a blank line: detached, not documentation
        start_line = previous_start
    return start_line


def _definition_span(siblings: list[Node], *, index: int, covered: list[bool], symbol: str) -> Span:
    """One definition's span, widened back over what documents it."""
    node = siblings[index]
    start, end = line_span(node)
    start = _extend_back(siblings, index=index, start_line=start)
    mark_covered(covered, start=start, end=end)
    return Span(start_line=start, end_line=end, symbol=symbol, node_type=node.type)


def _body(node: Node) -> list[Node]:
    """What a container holds: the children of its `do` block."""
    block = next((c for c in node.named_children if c.type == "do_block"), None)
    return list(block.named_children) if block is not None else []


def _walk(siblings: list[Node], covered: list[bool], prefix: str, depth: int) -> list[Span]:
    """Claim definitions among these siblings, descending into modules."""
    if depth > _MAX_NESTING:
        return []
    found: list[Span] = []
    for index, child in enumerate(siblings):
        keyword = _keyword(child)
        if keyword is None:
            continue
        name = _name(child)
        if name is None:
            continue  # error recovery: let the gap pass take the lines
        if keyword in _CONTAINERS:
            # `prefix` already carries its own trailing dot, so a nested
            # module concatenates rather than joins — otherwise
            # `defmodule Outer` around `defmodule Inner` reads `Outer..Inner`.
            found += _walk(_body(child), covered, f"{prefix}{name}.", depth + 1)
        elif keyword in _DEFINITIONS:
            found.append(
                _definition_span(siblings, index=index, covered=covered, symbol=f"{prefix}{name}")
            )
    return found


def spans(root: Node, lines: list[str], covered: list[bool]) -> list[Span]:
    """Claim Elixir's definitions; module headers become gaps.

    Args:
        root: Root of the parsed file; may be partial, since the parser
            is error tolerant.
        lines: The file's lines, unused — the look-behind works off
            sibling nodes and their line numbers.
        covered: Shared line-coverage bookkeeping, marked through
            `_definition_span`.

    Returns:
        One span per function, macro or guard, qualified by the modules
        that contain it.
    """
    del lines
    return _walk(list(root.named_children), covered, "", 0)
