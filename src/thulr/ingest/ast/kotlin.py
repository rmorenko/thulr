"""Kotlin policy: classes and objects hold members, top-level funs stand alone.

Kotlin keeps a type's members in a `class_body` child rather than a
`body` field, which is what `NestedPolicy.body_types` exists for. There
is no namespace to recurse into: `package` is a header, not a container,
so a file's declarations are already at the top level.

An `interface` parses as a `class_declaration` here, so it needs no row
of its own — it simply arrives with the classes.

Doc comments are attached: `block_comment` and `line_comment`. They were not, and that was the
half of this policy nobody had filled in — KDoc above a
definition is how this language documents it, and left unattached it
became a chunk of its own holding the most searchable sentence about
the thing, filed apart from the thing. Measured the same week: taking
prose out of what the embedder reads costs 31 answers of 98, while
taking the code body out costs nothing.
"""

from thulr.ingest.ast.nested import NestedPolicy, extractor

POLICY = NestedPolicy(
    types=("class_declaration", "object_declaration"),
    members=("function_declaration", "property_declaration", "secondary_constructor"),
    standalone=("function_declaration",),
    body_types=("class_body", "enum_class_body"),
    preamble=("block_comment", "line_comment"),
)

spans = extractor(POLICY)
