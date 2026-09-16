"""Objective-C policy: names live in children, not in fields.

The one language here that `NestedPolicy` cannot express, and for a dull
reason rather than an interesting one: nothing carries a `name` field.
A `class_implementation` keeps its name as the first `identifier` child,
a method keeps its as the first `identifier` inside a `method_definition`
under an `implementation_definition`, and a C function keeps its behind
a `function_declarator`'s `declarator`. Three shapes, three lookups, and
`symbol_name` can do none of them.

Methods are named by the first selector part — `valueAt`, not
`valueAt:index:`. The full selector is the honest name of an
Objective-C method and the wrong one to store: a reader asking where
`valueAt` is used types the word, and `normalised` folds a colon out of
existence anyway, so the longer form would buy nothing and match less.

`.h` is deliberately left to C. A header may be C, C++ or Objective-C
and nothing in the suffix says which; claiming it here would take every
C project's headers away from the language that can actually parse them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wsindex.ingest.ast.core import Span, gap_spans, line_span, mark_covered

if TYPE_CHECKING:
    from tree_sitter import Node

_TYPES = ("class_implementation", "class_interface", "category_implementation")
"""What holds methods. A category is an implementation too, and naming it
for the class it extends puts its methods under that class's symbol."""

_MEMBERS = ("implementation_definition", "method_declaration", "property_declaration")


def _first_identifier(node: Node) -> str | None:
    """The first `identifier` among a node's children, or None."""
    for child in node.named_children:
        if child.type == "identifier" and child.text is not None:
            return child.text.decode()
    return None


def _member_name(node: Node) -> str | None:
    """A method's first selector part, found one level down if need be."""
    found = _first_identifier(node)
    if found is not None:
        return found
    for child in node.named_children:
        found = _first_identifier(child)
        if found is not None:
            return found
    return None


def _function_name(node: Node) -> str | None:
    """A plain C function's name, behind its declarator."""
    declarator = next(
        (c for c in node.named_children if c.type == "function_declarator"),
        None,
    )
    if declarator is None:
        return None
    inner = declarator.child_by_field_name("declarator")
    if inner is not None and inner.text is not None:
        return inner.text.decode()
    return _first_identifier(declarator)


def _extend_back(siblings: list[Node], *, index: int, start_line: int) -> int:
    """Pull the comment block above a declaration into its span."""
    for previous in reversed(siblings[:index]):
        if previous.type not in ("comment", "multiline_comment"):
            break
        previous_start, previous_end = line_span(previous)
        if previous_end < start_line - 1:
            break
        start_line = previous_start
    return start_line


def spans(root: Node, lines: list[str], covered: list[bool]) -> list[Span]:
    """Claim classes as their methods, and free functions whole.

    Args:
        root: Root of the parsed file; may be partial.
        lines: The file's lines, for the gap pass over a class's own
            lines once its methods are taken.
        covered: Shared line-coverage bookkeeping.

    Returns:
        One span per method, qualified by its class, plus the class's
        remainder and any C functions standing alone.
    """
    found: list[Span] = []
    children = root.named_children
    for index, child in enumerate(children):
        if child.type == "function_definition":
            name = _function_name(child)
            if name is None:
                continue
            start, end = line_span(child)
            start = _extend_back(children, index=index, start_line=start)
            mark_covered(covered, start=start, end=end)
            found.append(Span(start_line=start, end_line=end, symbol=name, node_type=child.type))
            continue
        if child.type not in _TYPES:
            continue
        owner = _first_identifier(child)
        if owner is None:
            continue  # error recovery: let the gap pass take the lines
        members = child.named_children
        for position, member in enumerate(members):
            if member.type not in _MEMBERS:
                continue
            name = _member_name(member)
            if name is None:
                continue
            start, end = line_span(member)
            start = _extend_back(members, index=position, start_line=start)
            mark_covered(covered, start=start, end=end)
            found.append(
                Span(
                    start_line=start,
                    end_line=end,
                    symbol=f"{owner}.{name}",
                    node_type=member.type,
                )
            )
        start, end = line_span(child)
        found += gap_spans(
            lines, covered=covered, start=start, end=end, symbol=owner, node_type=child.type
        )
    return found
