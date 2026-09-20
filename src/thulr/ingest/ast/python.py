"""Python policy: decorated defs unwrap, methods get qualified symbols.
Doc comments are attached: `comment`. They were not, and that was the
half of this policy nobody had filled in — a `#` block above a
definition is how this language documents it, and left unattached it
became a chunk of its own holding the most searchable sentence about
the thing, filed apart from the thing. Measured the same week: taking
prose out of what the embedder reads costs 31 answers of 98, while
taking the code body out costs nothing.
"""

from __future__ import annotations

from thulr.ingest.ast.nested import NestedPolicy, extractor

POLICY = NestedPolicy(
    types=("class_definition",),
    members=("function_definition",),
    standalone=("function_definition",),
    wrappers=("decorated_definition",),
    preamble=("comment",),
)
"""`function_definition` is both a member and standalone: the same node
is a method inside a class and a function outside one. Decorators wrap
the definition, so the chunk is the wrapper — a decorator without what it
decorates is not a passage anyone wants back."""

spans = extractor(POLICY)
"""Functions and methods with a qualified symbol (`Cls.method`); class
lines no method claimed — the header, the docstring, the attributes —
carry the class name. Oversized functions stay whole on purpose."""
