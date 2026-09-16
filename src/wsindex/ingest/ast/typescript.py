"""TypeScript policy: export wrappers unwrap, arrow consts count as functions.
Doc comments are attached: `comment`. They were not, and that was the
half of this policy nobody had filled in — JSDoc above a
definition is how this language documents it, and left unattached it
became a chunk of its own holding the most searchable sentence about
the thing, filed apart from the thing. Measured the same week: taking
prose out of what the embedder reads costs 31 answers of 98, while
taking the code body out costs nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wsindex.ingest.ast.core import Span, line_span, mark_covered, symbol_name, unwrap
from wsindex.ingest.ast.nested import NestedPolicy, extractor

if TYPE_CHECKING:
    from tree_sitter import Node

POLICY = NestedPolicy(
    types=("class_declaration",),
    members=("method_definition",),
    standalone=(
        "function_declaration",
        "interface_declaration",
        "type_alias_declaration",
        "enum_declaration",
    ),
    wrappers=("export_statement",),
    preamble=("comment",),
)
"""The export keyword stays inside the chunk: `export function f` is one
declaration, and a chunk holding only the word `export` would be found by
nobody."""

_FUNCTION_VALUES = ("arrow_function", "function_expression")
"""What makes a `const` a definition rather than a constant. This is the
one rule the shared walk cannot express, because it is about a node's
*value* and not its type."""

_declarations = extractor(POLICY)


def _extend_back(siblings: list[Node], *, index: int, start_line: int) -> int:
    """Widen back over the JSDoc above a declaration; a blank line ends it."""
    for previous in reversed(siblings[:index]):
        if previous.type != "comment":
            break
        previous_start, previous_end = line_span(previous)
        if previous_end < start_line - 1:
            break
        start_line = previous_start
    return start_line


def _const_function(siblings: list[Node], index: int, covered: list[bool]) -> Span | None:
    """A `const f = () => ...` as a definition; None for a plain constant."""
    child = siblings[index]
    node = unwrap(node=child, wrapper="export_statement", inner=("lexical_declaration",))
    if node.type != "lexical_declaration":
        return None
    declarator = next((c for c in node.named_children if c.type == "variable_declarator"), None)
    if declarator is None:
        return None
    value = declarator.child_by_field_name("value")
    if value is None or value.type not in _FUNCTION_VALUES:
        return None  # a plain constant is a legitimate gap
    name = symbol_name(declarator)
    if name is None:
        return None
    start, end = line_span(child)
    start = _extend_back(siblings, index=index, start_line=start)
    mark_covered(covered, start=start, end=end)
    return Span(start_line=start, end_line=end, symbol=name, node_type="lexical_declaration")


def spans(root: Node, lines: list[str], covered: list[bool]) -> list[Span]:
    """Declarations by the shared walk, plus the consts that are functions.

    Two passes rather than one branchy loop: everything typescript shares
    with python and java goes through the same code those use, and what
    is left is the single rule that is typescript's own.

    Deliberate gap: anonymous default exports. JSDoc is not one — this
    path used to skip the look-behind while the shared walk did it, so
    `/** A React hook. */` above `export const useTitle = () => {}` was
    filed apart from it. That spelling is how modern TypeScript declares
    a function, and the comment above it is the sentence a search for
    "hook for the title" is trying to match.
    """
    children = root.named_children
    found = _declarations(root, lines, covered)
    found += [
        span
        for span in (_const_function(children, i, covered) for i in range(len(children)))
        if span is not None
    ]
    return found
