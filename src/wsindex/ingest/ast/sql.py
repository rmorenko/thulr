"""SQL policy: what a migration creates, named as the database names it.

Every top-level statement arrives as a `statement` wrapping one node
that says what it is — `create_table`, `create_view`, `create_index`,
`create_function`. Those four are claimed; a `SELECT` or an `INSERT`
falls to the gap pass, which is right, because a query is not a thing
another file can refer to by name and a table is.

The name is taken as the first `object_reference` or `identifier` after
the keywords rather than from a field, because the grammar does not
offer one and the keyword count varies: `CREATE TABLE x` has two,
`CREATE OR REPLACE VIEW x` has four.

Named `app_user`, not `table.app_user`. The prefix would read well and
break the one thing this earns: `normalised` folds a name to letters and
digits, so a stored `table.app_user` becomes `tableappuser` and stops
matching the `app_user` somebody wrote in code. What sort of object it
is goes in `node_type`, where it costs nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wsindex.ingest.ast.core import Span, line_span, mark_covered

if TYPE_CHECKING:
    from tree_sitter import Node

_CREATES = ("create_table", "create_view", "create_index", "create_function", "create_type")
"""Statements that introduce something the rest of a codebase can name.
`create_type` is in for Postgres enums, which application code reads by
name as often as it reads a table."""

_NAMES = ("object_reference", "identifier")
"""Where a name hides once the keywords are done with."""


def _named(node: Node) -> str | None:
    """The object a `CREATE` introduces, or None on a damaged tree."""
    for child in node.named_children:
        if child.type in _NAMES and child.text is not None:
            return child.text.decode().strip('"`[]')
    return None


def _extend_back(siblings: list[Node], *, index: int, start_line: int) -> int:
    """Pull `--` comment lines into the statement they describe.

    A migration's only documentation is the comment above it, and a
    blank line detaches — the same rule Go's doc comments follow.
    """
    for previous in reversed(siblings[:index]):
        if previous.type != "comment":
            break
        previous_start, previous_end = line_span(previous)
        if previous_end < start_line - 1:
            break
        start_line = previous_start
    return start_line


def spans(root: Node, lines: list[str], covered: list[bool]) -> list[Span]:
    """Claim what the file creates; queries become gaps.

    Args:
        root: Root of the parsed file; may be partial.
        lines: The file's lines, unused — the look-behind works off
            sibling nodes and their line numbers.
        covered: Shared line-coverage bookkeeping.

    Returns:
        One span per created object, named as the database names it.
    """
    del lines
    found: list[Span] = []
    children = root.named_children
    for index, child in enumerate(children):
        inner = next((c for c in child.named_children if c.type in _CREATES), None)
        if inner is None:
            continue
        name = _named(inner)
        if name is None:
            continue  # error recovery: let the gap pass take the lines
        start, end = line_span(child)
        start = _extend_back(children, index=index, start_line=start)
        mark_covered(covered, start=start, end=end)
        found.append(Span(start_line=start, end_line=end, symbol=name, node_type=inner.type))
    return found
