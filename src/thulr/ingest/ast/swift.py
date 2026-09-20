"""Swift policy: four declaration words, one node type behind them.

`struct`, `class`, `enum` and `extension` all arrive as
`class_declaration` with a `name` field, which makes the grammar kinder
here than the language looks. An extension is named for the type it
extends, so `extension Board { func clear() }` yields `Board.clear` and
joins the rest of `Board`'s surface under one symbol — which is what
somebody asking `--symbol Board` means, and the reason not to invent a
separate name for it.

The body is a child rather than a field, and comes in two shapes:
`class_body` for the first three words and `enum_class_body` for enums.
Both are listed, so an enum's cases are reachable.

`property_declaration` sits beside `function_declaration` in members
because Swift's stored properties are where a type's configuration
lives, and `Board.cells` is a thing worth being able to ask about.

`///` documentation is a sibling comment, attached the way Go's is.
"""

from thulr.ingest.ast.nested import NestedPolicy, extractor

POLICY = NestedPolicy(
    types=("class_declaration", "protocol_declaration"),
    members=(
        "function_declaration",
        "property_declaration",
        "enum_entry",
        "protocol_function_declaration",
        "protocol_property_declaration",
        "init_declaration",
    ),
    standalone=("function_declaration", "property_declaration"),
    body_types=("class_body", "enum_class_body", "protocol_body"),
    preamble=("comment", "multiline_comment"),
)

spans = extractor(POLICY)
