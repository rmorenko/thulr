"""PHP policy: namespaces recurse, classes and traits hold their methods.

A namespace can be braced or file-scoped; only the braced form is a node
with a body to descend into, and the file-scoped form leaves its
declarations at the top level, so both are covered without a special case.

Traits and interfaces are types rather than standalone: a trait exists to
carry methods, and searching for one method of it is the normal case.

Doc comments are attached: `comment`. They were not, and that was the
half of this policy nobody had filled in — PHPDoc above a
definition is how this language documents it, and left unattached it
became a chunk of its own holding the most searchable sentence about
the thing, filed apart from the thing. Measured the same week: taking
prose out of what the embedder reads costs 31 answers of 98, while
taking the code body out costs nothing.
"""

from wsindex.ingest.ast.nested import NestedPolicy, extractor

POLICY = NestedPolicy(
    containers=("namespace_definition",),
    types=("class_declaration", "trait_declaration", "interface_declaration"),
    members=("method_declaration",),
    standalone=("function_definition", "enum_declaration"),
    preamble=("comment",),
)

spans = extractor(POLICY)
