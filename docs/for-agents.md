# wsindex for agents, and for the person wiring one up

## What an agent gets

Three tools over MCP (`wsindex mcp`, stdio), and the interesting one is
`search`:

```
search(query, k=10, repo=, lang=, kind=, path=, symbol=, budget=)
refs(name)     — which config declares a setting and what names it in
                 code, across spellings (max_retries = MaxRetries); where
                 a symbol is defined and which files name it, each use
                 labelled call/code/import/string/comment, calls first
why(symbol)    — the commits that wrote a definition, and their messages
```

It answers with `file:line` and the chunk text, which is what an agent
needs to decide whether to open the file.

## The two fields that exist because of agents

**`budget` caps the answer in tokens, which `k` cannot.** Ten hits are
anywhere between four hundred tokens and eight thousand depending on what
they are, and an agent filling a context window cannot spend "ten hits".
Given a budget, the reply carries `tokens` actually spent and
`dropped_for_budget` — so the agent knows it was cut rather than knowing
nothing.

**`unsearched` names repositories that were never indexed.** An agent
reporting "there is no such code" about a workspace half of which was
never read is worse than an agent saying it does not know. Every reply
carries this list, empty or not.

Both are in the reply shape, not in prose somewhere: an agent does not
read a README.

## What it costs you

The search itself is free and local: no API, no key, no tokens. What
costs tokens is the answer arriving in your agent's context, and that is
the number `budget` exists to control.

Indexing costs minutes once (a 2 000-file repository in 37 seconds,
11 800 files in four minutes) and under a second per re-index after,
whatever the corpus size. Nothing leaves the machine unless you
explicitly configure a remote model — see [for-security.md](for-security.md).

## What has not been measured, and it is the question you care about

**Whether an agent with wsindex beats the same agent with `grep`.** That
comparison has not been run, and it is the one that matters: everything
measured here ranks *hits*, and a rank is not a task finished with fewer
tokens.

What *is* measured is the ranking, against `ripgrep` on 154 questions
taken from the issue trackers of the indexed projects — nobody here wrote
them. Right file in the top ten: fully local **55**, ripgrep **60**,
local with hybrid retrieval **64**, and with a hosted reranker **85**.
So the default ties grep and the configured version beats it by a
distance, which is worth knowing before you wire anything up.

The number an agent should care about most: of those 154 questions,
`ripgrep` returned **more than twenty files for 72 of them**, median
seventy. Those are the questions where a ranked answer is the difference
between reading three files and reading seventy — and they are nearly
half of what real people ask. Fully local turns 23 of those 72 into a
top-ten answer; with a hosted reranker, 33.

Wire this up where your agent's greps come back with hundreds of matches.
That is where the measured advantage is, and it is now a measured number
rather than a claim.

## Determinism

Same query, same index, same result: the ids are a hash of content and
path, and search is an exact scan up to about a million chunks. An agent
that replays its own runs gets the same answers. Turning on a reranker
keeps this true; turning on a *remote* model makes it somebody else's
promise rather than this project's.

## Wiring it up

```jsonc
// Claude Code, .mcp.json
{
  "mcpServers": {
    "wsindex": { "command": "wsindex", "args": ["mcp"] }
  }
}
```

The server reads the workspace config the same way the CLI does, so
whatever `wsindex status` shows is what the agent will search.
