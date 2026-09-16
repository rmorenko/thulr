"""Java policy: classes hold members, annotations come for free.
Doc comments are attached: `block_comment` and `line_comment`. They were not, and that was the
half of this policy nobody had filled in — Javadoc above a
definition is how this language documents it, and left unattached it
became a chunk of its own holding the most searchable sentence about
the thing, filed apart from the thing. Measured the same week: taking
prose out of what the embedder reads costs 31 answers of 98, while
taking the code body out costs nothing.
"""

from __future__ import annotations

from wsindex.ingest.ast.nested import NestedPolicy, extractor

POLICY = NestedPolicy(
    types=("class_declaration",),
    members=("method_declaration", "constructor_declaration"),
    standalone=("interface_declaration", "enum_declaration", "record_declaration"),
    preamble=("block_comment", "line_comment"),
)
"""Annotations live inside the declaration node (its `modifiers` child),
so spans include them without asking. Javadoc comments are siblings and
stay in gap chunks — accepted debt, like JSDoc for typescript."""

spans = extractor(POLICY)
"""Classes descend into methods and constructors (`Cls.method`);
interfaces, enums and records stay whole."""
