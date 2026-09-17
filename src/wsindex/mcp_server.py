"""MCP: the workspace index as tools an agent can call.

The answer to "is there an IDE plugin": an agent client speaks MCP
already, so no plugin has to exist. Point it at `wsindex mcp`.

Three tools — `search`, `refs`, `why` — the three commands worth calling
from outside. `index` is deliberately absent: a tool an agent may call
again without thinking should not be minutes of CPU and somebody's git
remotes.

`build()` knows nothing about transport. `wsindex mcp` runs it over
stdio, which is what an editor spawns; `wsindex serve` mounts the same
object on HTTP. One implementation of the tools, two ways in.

**Who this is for, measured.** Nine runs against a headless agent say
these tools do not help one that has the repositories on disk. Fixing
harvested bugs: no gain, six ways. Answering "where does this live" on
26 questions: 16 right without the tools, 15 with the local embedder, 16
with the hosted one. The same 26 with the shell taken away, so the agent
had `Read` and `Glob` and nothing else: 13 without, 13 with. Removing
grep cost the control three answers and cost this server's caller the
same three.

The reason is in the transcripts and it is not a retrieval failure. The
agent called these tools in every single run, and they put the right
file in front of it 69% of the time on the local embedder, 81% hosted,
96% once grep was gone. What did not move was the answer. An agent that
can open files reaches them anyway; the retrieval it cannot do for
itself is not the part it is short of.

So the caller these tools are for is the one that cannot open a file —
an agent with no filesystem and no git, for which this is the only way
in. That is why `k` defaults higher here than in the CLI, and why the
reply carries `unsearched`: both are for a caller that cannot check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from wsindex.links import KIND_LABELS, OCCURRENCE_ORDER, LinkKind
from wsindex.model import Kind, SearchFilter

if TYPE_CHECKING:  # pragma: no cover - import-time only, for annotations
    from mcp.server.fastmcp import FastMCP

    from wsindex.pipeline import Pipeline

INSTRUCTIONS = """\
Semantic search over the repositories of a developer workspace. Results
carry exact file:line locations, so quote them rather than paraphrasing.

Use `search` for "where/how does X work" questions; narrow it with
`repo`, `lang`, `kind` or `path` when the workspace is large. Use `refs`
to find everything that names a port, a ticket or a commit, and `why` to
find the commits that wrote a definition — that is usually where the
reasoning behind a design lives.
"""


def build(pipeline: Pipeline | None = None) -> FastMCP:
    """Assemble the MCP server over one shared Pipeline.

    Args:
        pipeline: Already built, or None to build the CLI's — the same
            composition root the server and the shell use, so no
            interface gets its own engine.

    Returns:
        The server, ready for either transport.
    """
    from mcp.server.fastmcp import FastMCP

    if pipeline is None:
        from wsindex.cli import build_pipeline

        pipeline = build_pipeline()
    engine = pipeline
    server: FastMCP = FastMCP(name="wsindex", instructions=INSTRUCTIONS)

    @server.tool()
    def search(
        query: Annotated[str, Field(description="What to look for, in natural language")],
        # Twenty, where the CLI's is ten, and the difference is the
        # caller. A person reads `file:line` and opens the file; this
        # caller may have no file to open, and then the reply is the
        # whole answer. Asked on 135 questions with line-level truth —
        # does what came back *contain* the lines the fix changed —
        # against the median lines of text a reply carries:
        #
        #   k=10   74 answered,   515 lines     k=10   44,  261  (local)
        #   k=20   92 answered,   956 lines     k=20   57,  509
        #   k=30   98 answered,  1371 lines     k=30   66,  720
        #
        # Twenty is the knee on the hosted model: the step to it buys an
        # answer per 24 lines, the step past it one per 69. A caller that
        # can open files should pass a smaller k, one that cannot should
        # pass 30 — and the description says so, because an agent does
        # not read this comment.
        k: Annotated[
            int,
            Field(
                description=(
                    "How many hits. Lower it to 10 if you can open the files yourself; "
                    "raise it to 30 if this reply is all you will see of the code"
                ),
                ge=1,
                le=50,
            ),
        ] = 20,
        repo: Annotated[str | None, Field(description="Restrict to one repo id")] = None,
        lang: Annotated[list[str] | None, Field(description="Languages (OR)")] = None,
        kind: Annotated[
            list[str] | None, Field(description="code, config, doc or commit (OR)")
        ] = None,
        path: Annotated[str | None, Field(description="Path glob, e.g. src/*.py")] = None,
        symbol: Annotated[str | None, Field(description="Substring of the symbol name")] = None,
        # None by default, and measured rather than assumed. An answer
        # costs about 2 200 tokens at k=10, which looks like something to
        # cap until the cap is swept: `fit` drops whole hits, so on 204
        # harvested questions a 1 200-token budget keeps the answer for
        # 70 where no budget keeps it for 98, and 800 keeps 53. Half the
        # tokens cost 28 answers. A caller who knows its own context
        # window can still say so; this is not a default worth having.
        #
        # It is also the right knob now that `k` defaults higher: a
        # caller that wants less should cap the tokens and let the tail
        # of the ranking go, rather than ask for fewer hits and get the
        # same narrow slices of the same few files.
        budget: Annotated[
            int | None,
            Field(description="Cap the returned text at this many tokens", ge=1),
        ] = None,
    ) -> dict[str, Any]:
        """Search the workspace by meaning; returns chunks with file:line."""
        return _search(
            engine,
            query,
            k=k,
            repo=repo,
            lang=lang,
            kind=kind,
            path=path,
            symbol=symbol,
            budget=budget,
        )

    @server.tool()
    def refs(
        name: Annotated[str, Field(description="A port, ticket, commit sha or url")],
    ) -> dict[str, Any]:
        """Everything that names this: who reads a port, which commits mention a ticket."""
        return _refs(engine, name)

    @server.tool()
    def why(
        # Still `symbol`, though it now takes a place as well. The name
        # is the wire format: a client that already calls this passes
        # `symbol`, and renaming an argument to describe it better is a
        # break in exchange for a nicer word.
        symbol: Annotated[
            str,
            Field(description="A function, class or method name, or `path/to/file.py:42`"),
        ],
    ) -> dict[str, Any]:
        """The commits that wrote a definition, and what they said about it."""
        return _why(engine, symbol)

    return server


# The three tool bodies. Out of `build` because the factory should read
# as the list of tools it registers — what each one answers is a
# question of its own. Each is a library call plus a rendering, which is
# ADR-10's rule read from this side.


def _search(
    engine: Pipeline,
    query: str,
    *,
    k: int,
    repo: str | None,
    lang: list[str] | None,
    kind: list[str] | None,
    path: str | None,
    symbol: str | None,
    budget: int | None = None,
) -> dict[str, Any]:
    """`search`, as data.

    `budget` is the one thing `k` cannot say. Ten hits are anywhere
    between two hundred tokens and twelve thousand depending on what they
    contain, and the caller finds out only after spending them — which
    matters here and nowhere else, because this caller is a model with a
    context window rather than a person with a screen. What was dropped
    is named in the answer, the way `unsearched` is: a trimmed result
    that does not say it was trimmed is a result an agent will report as
    complete.

    Raises:
        ValueError: `kind` names something that is not a Kind. Named back
            to the caller so an agent can fix it on its next turn.
    """
    try:
        kinds = tuple(Kind(value) for value in kind or ())
    except ValueError as exc:
        raise ValueError(f"kind must be one of {', '.join(k.value for k in Kind)}") from exc
    candidate = SearchFilter(lang=tuple(lang or ()), kind=kinds, path=path, symbol=symbol)
    hits = engine.search(query, k=k, repo=repo, filters=None if candidate.is_empty else candidate)
    spent = None
    dropped = 0
    if budget is not None:
        fitted, spent = engine.fit(hits, budget=budget)
        dropped = len(hits) - len(fitted)
        hits = fitted
    return {
        "count": len(hits),
        "hits": [hit.to_json() for hit in hits],
        **({"tokens": spent, "dropped_for_budget": dropped} if budget is not None else {}),
        # Named, because an agent reporting "there is no such code" about
        # a workspace half of which was never indexed is worse than an
        # agent that says it does not know.
        "unsearched": list(engine.unsearched(repo)),
    }


def _refs(engine: Pipeline, name: str) -> dict[str, Any]:
    """`refs`, as data, with the drift flag the CLI also reports."""
    edges = engine.references(name)
    # Most useful first, because an agent reads a prefix of this and
    # stops: definitions before uses, and within uses, calls before type
    # references before comments. The CLI groups by relation to get the
    # same order; here the list is flat, so it has to be sorted.
    order = list(KIND_LABELS)
    edges = sorted(
        edges,
        key=lambda edge: (
            order.index(edge.kind),
            edge.name != name,
            OCCURRENCE_ORDER[edge.via] if edge.via else 0,
        ),
    )
    found = [
        {
            "relation": KIND_LABELS[edge.kind],
            "repo": edge.repo,
            "path": edge.path,
            "line": edge.line,
            "url": edge.url,
            # The spelling actually found, which is not always the one
            # asked for: `max_retries` in a config is `MaxRetries` in the
            # code. An agent told only the line number would report the
            # match as if the two files agreed.
            "name": edge.name,
            # None for every relation but "named in". Present regardless
            # so the shape does not change under an agent mid-list.
            "via": edge.via.value if edge.via else None,
        }
        for edge in edges
    ]
    drifted = any(edge.kind is LinkKind.READS_KEY for edge in edges) and not any(
        edge.kind is LinkKind.DECLARES for edge in edges
    )
    return {"name": name, "count": len(found), "links": found, "unresolved": drifted}


def _why(engine: Pipeline, target: str) -> dict[str, Any]:
    """`why`, as data. The definitions come from the library, whole."""
    return {
        "symbol": target,
        "definitions": [
            {
                "symbol": definition.hit.symbol,
                "repo": definition.hit.repo,
                "path": definition.hit.path,
                "start_line": definition.hit.start_line,
                "end_line": definition.hit.end_line,
                "commits": [
                    {
                        "commit": author.commit,
                        "message": author.message,
                        "references": [
                            {"name": ref.name, "url": ref.url} for ref in author.references
                        ],
                    }
                    for author in definition.commits
                ],
            }
            for definition in engine.why(target)
        ],
    }


__all__ = ["INSTRUCTIONS", "build"]
