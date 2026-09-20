"""HCL policy: one chunk per block, named the way Terraform addresses it.

An HCL file is a `body` of `block`s, and a block is an identifier saying
what sort it is followed by zero or more quoted labels:
`resource "aws_lb" "public" { ... }`, `variable "region" { ... }`.

The labels are the name, joined with a dot — `aws_lb.public`, `region` —
because that is the string Terraform itself uses to refer to the thing
and therefore the string a person types when they ask where it is. The
block's own word goes in `node_type`, so `resource` and `variable` stay
distinguishable without entering the symbol.

Not prefixed with that word, for the same reason SQL is not prefixed
with `table`: `normalised` folds a name to letters and digits, and
`resource.aws_lb.public` becomes `resourceawslbpublic`, which matches
nothing anybody wrote.

A block with no labels — `terraform { }`, `locals { }` — is named by its
word, since that is the only name it has and there is exactly one of
each per file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from thulr.ingest.ast.core import Span, line_span, mark_covered

if TYPE_CHECKING:
    from tree_sitter import Node

_MAX_NESTING = 8
"""How deep nested blocks are followed. Real configuration nests two or
three levels; a bound keeps a damaged tree from costing a run."""


def _label(node: Node) -> str | None:
    """A block's Terraform address, or None if it cannot be read."""
    word = next((c for c in node.named_children if c.type == "identifier"), None)
    if word is None or word.text is None:
        return None
    labels = [
        c.text.decode().strip('"')
        for c in node.named_children
        if c.type == "string_lit" and c.text is not None
    ]
    return ".".join(labels) if labels else word.text.decode()


def _kind(node: Node) -> str:
    word = next((c for c in node.named_children if c.type == "identifier"), None)
    return word.text.decode() if word is not None and word.text is not None else "block"


def _extend_back(siblings: list[Node], *, index: int, start_line: int) -> int:
    """Pull `#` and `//` comment lines into the block below them."""
    for previous in reversed(siblings[:index]):
        if previous.type != "comment":
            break
        previous_start, previous_end = line_span(previous)
        if previous_end < start_line - 1:
            break
        start_line = previous_start
    return start_line


def _flat(nodes: list[Node], depth: int) -> list[Node]:
    """This level in document order, with `body` wrappers spliced out.

    A file is `[comment, body[block, block]]`, so a comment written
    above the first block is not among that block's siblings — it is a
    sibling of the `body` that holds it. Walking the wrapper as its own
    level put the comment in a chunk of its own and left the resource it
    describes undocumented, which is the one thing the look-behind
    exists to prevent.
    """
    if depth > _MAX_NESTING:
        return []
    out: list[Node] = []
    for node in nodes:
        if node.type == "body":
            out += _flat(node.named_children, depth + 1)
        else:
            out.append(node)
    return out


def _walk(nodes: list[Node], covered: list[bool]) -> list[Span]:
    """Claim every block, in document order."""
    found: list[Span] = []
    for index, child in enumerate(nodes):
        if child.type != "block":
            continue
        name = _label(child)
        if name is None:
            continue  # error recovery: let the gap pass take the lines
        start, end = line_span(child)
        start = _extend_back(nodes, index=index, start_line=start)
        mark_covered(covered, start=start, end=end)
        found.append(Span(start_line=start, end_line=end, symbol=name, node_type=_kind(child)))
    return found


def spans(root: Node, lines: list[str], covered: list[bool]) -> list[Span]:
    """Claim every top-level block; stray attributes become gaps.

    Args:
        root: Root of the parsed file; may be partial.
        lines: The file's lines, unused.
        covered: Shared line-coverage bookkeeping.

    Returns:
        One span per block, named as Terraform addresses it.
    """
    del lines
    return _walk(_flat(list(root.named_children), 0), covered)
