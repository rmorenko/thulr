"""Shell policy: functions, with the `#` lines that explain them.

The smallest extractor here, because the language gives it little to do.
A shell script has one nesting level worth naming — `function_definition`
— and both spellings, `deploy() { }` and `function deploy { }`, arrive as
that same node with the name in its `name` field.

Everything else falls to the gap pass on purpose. A script's top-level
assignments are its settings, and windowing them together is the right
shape for `ARTIFACT_DIR=...` followed by six more of its kind; a chunk
per assignment would file each away from its neighbours.

Doc comments are pulled in the way Go's are, and by the same rule: a
blank line detaches. A shell script's only documentation is the `#`
block above a function, and leaving it as a chunk of its own files the
sentence that describes a function apart from the function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from thulr.ingest.ast.core import Span, line_span, mark_covered, symbol_name

if TYPE_CHECKING:
    from tree_sitter import Node


def _extend_back(siblings: list[Node], *, index: int, start_line: int) -> int:
    """Pull a function's `#` comment block into its span.

    The shebang is a comment too, and it sits above the first thing in
    the file — but a blank line almost always separates it, and where it
    does not, a line naming the interpreter is no worse in a chunk than
    on its own.
    """
    for previous in reversed(siblings[:index]):
        if previous.type != "comment":
            break
        previous_start, previous_end = line_span(previous)
        if previous_end < start_line - 1:
            break  # a blank line: a detached comment, not documentation
        start_line = previous_start
    return start_line


def spans(root: Node, lines: list[str], covered: list[bool]) -> list[Span]:
    """Claim the script's functions; the rest becomes gaps.

    Args:
        root: Root of the parsed file; may be partial, since the parser
            is error tolerant.
        lines: The file's lines, unused — the look-behind works off
            sibling nodes and their line numbers.
        covered: Shared line-coverage bookkeeping.

    Returns:
        One span per function, named as the script names it.
    """
    del lines
    found: list[Span] = []
    children = root.named_children
    for index, child in enumerate(children):
        if child.type != "function_definition":
            continue
        name = symbol_name(child)
        if name is None:
            continue  # error recovery: let the gap pass take the lines
        start, end = line_span(child)
        start = _extend_back(children, index=index, start_line=start)
        mark_covered(covered, start=start, end=end)
        found.append(Span(start_line=start, end_line=end, symbol=name, node_type=child.type))
    return found
