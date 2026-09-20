"""C# policy: namespaces recurse, classes and structs hold their members.

Everything nests under a namespace — file-scoped (`namespace App;`) or
braced — so the walk has to descend or a whole file yields one chunk.
Records and enums are claimed whole: a record's members are its
constructor parameters, and splitting an enum by member would produce
chunks too small to mean anything.

Doc comments are attached: `comment`. They were not, and that was the
half of this policy nobody had filled in — `///` XML documentation above a
definition is how this language documents it, and left unattached it
became a chunk of its own holding the most searchable sentence about
the thing, filed apart from the thing. Measured the same week: taking
prose out of what the embedder reads costs 31 answers of 98, while
taking the code body out costs nothing.
"""

from thulr.ingest.ast.nested import NestedPolicy, extractor

POLICY = NestedPolicy(
    containers=("namespace_declaration", "file_scoped_namespace_declaration"),
    types=("class_declaration", "struct_declaration", "interface_declaration"),
    members=(
        "method_declaration",
        "constructor_declaration",
        "property_declaration",
        "operator_declaration",
    ),
    standalone=("record_declaration", "enum_declaration", "delegate_declaration"),
    preamble=("comment",),
)

spans = extractor(POLICY)
