"""Ruby policy: modules recurse, classes hold methods, `def` stands alone.

`def` is the node that makes the standalone/member distinction earn its
keep: inside a class it is a method and gets `Server.serve`, at the top
level or directly in a module it is a function and keeps its own name.
Listing it in both roles is how one node type covers both, since members
are only ever consulted inside a type body.

`singleton_method` (`def self.build`) is a method too — Ruby's class-level
one — so it is qualified the same way and answers `--symbol Server`.

Doc comments are attached: `comment`. They were not, and that was the
half of this policy nobody had filled in — a `#` block above a
definition is how this language documents it, and left unattached it
became a chunk of its own holding the most searchable sentence about
the thing, filed apart from the thing. Measured the same week: taking
prose out of what the embedder reads costs 31 answers of 98, while
taking the code body out costs nothing.
"""

from wsindex.ingest.ast.nested import NestedPolicy, extractor

POLICY = NestedPolicy(
    containers=("module",),
    types=("class",),
    members=("method", "singleton_method"),
    standalone=("method", "singleton_method"),
    preamble=("comment",),
)

spans = extractor(POLICY)
