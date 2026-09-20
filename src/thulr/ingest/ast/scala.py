"""Scala policy: three words for a type, and Scaladoc sits above it.

`class`, `trait` and `object` are one role here — something with a body
whose members deserve chunks of their own — and the language spells it
three ways. A `case class` is a `class_definition` with a modifier, so it
needs no entry.

`function_declaration` joins `function_definition` in `members` because
Scala writes an abstract method as a declaration with no body, and in a
trait that is most of the interesting surface: `def apply(c: HCursor):
Result[A]` is the whole contract of `Decoder`.

`val_definition` is listed and will often fail to name itself — the name
lives in a pattern rather than a `name` field, since Scala allows
`val (a, b) = pair`. Those fall to the gap pass and stay indexed, which
is the right outcome for a binding whose name is a destructuring.

`block_comment` is the preamble: Scaladoc is `/** ... */` directly above
what it documents, and left alone it becomes a chunk holding the single
most searchable sentence about a method, filed apart from the method.

This language is here because it is the one whose absence cost a
measurement. The field trial had to exclude `circe`, which indexed 67 of
its 455 files, for want of a grammar — the same silence Elixir caused,
in the one other workspace that hit it.
"""

from thulr.ingest.ast.nested import NestedPolicy, extractor

POLICY = NestedPolicy(
    containers=("package_clause",),
    types=("class_definition", "trait_definition", "object_definition"),
    members=(
        "function_definition",
        "function_declaration",
        "val_definition",
        "var_definition",
        "type_definition",
    ),
    standalone=(
        "function_definition",
        "function_declaration",
        "val_definition",
        "var_definition",
        "type_definition",
    ),
    preamble=("block_comment", "comment"),
)

spans = extractor(POLICY)
