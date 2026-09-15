# wsindex for agents, and for the person wiring one up

## What an agent gets

Three tools over MCP (`wsindex mcp`, stdio), and the interesting one is
`search`:

```
search(query, k=10, repo=, lang=, kind=, path=, symbol=, budget=)
refs(name)     — which config declares a setting and what names it in
                 code, across spellings (max_retries = MaxRetries), which
                 is the half that beats grep; also where a symbol is
                 defined and what names it, which does not
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

## What it costs to answer, which is the number you are here for

**Reaching the same answer costs about a tenth of the reading.** Over 204
tasks taken from the indexed projects' own issue trackers — the title of
a closed issue, and the files the pull request that closed it changed —
two workers were sent at each one under a single token budget. `grep`
read a window around every match, the way `rg -C` shows it; wsindex read
the line ranges it ranked. Both stopped when a file holding the answer
was in front of them.

|                                      |       wsindex |   grep |
| ------------------------------------ | ------------: | -----: |
| tasks found                          |           125 |    112 |
| median tokens, on the 102 both found |     **1 263** | 13 474 |
| mean                                 |         3 277 | 25 443 |
| cheaper                              | **89 of 102** |     13 |

Read the median twice: that is what lands in your context window to get
one answer.

**What that is not.** The worker is a fixed reading policy, not a
language model — an agent measures the model at least as much as the
tool, and runs twice it reads different files. This measures the size of
the pile each tool puts on the desk, which is the part the tool controls.
A real agent that skims, gives up on a file after two lines and rewrites
its query may do better with either.

What *is* measured is the ranking, against `ripgrep` on 204 questions
taken from the issue trackers of the indexed projects — nobody here wrote
them. Right file in the top ten: the local default **98**, ripgrep **71**,
with a hosted reranker **109** and a hosted embedder as well **132**. In
the top *three* it is 62 against ripgrep's 71, which is noise: the win is
at depth, not at the very top, and an agent that reads one hit and stops
will not see it.

Measured separately and worth knowing before you wire anything up: on 24
real issues, an agent given these tools finished on the same lines as
often as one without them and spent **more** tokens doing it — 19 of 24
tasks more expensive, p = 0.0066 locally. The ranking above is a fact
about search; it did not become a saving for an agent.

**Two answers here do beat `grep`, and both are now measured.** `why` —
a definition to the commits that wrote it — named a commit that really
touched those lines 161 times of 164, against `git log -S` at 146,
winning the discordant pairs 16 to 1. And `refs` reaching a setting
spelled one way in a config and another in code: 64 of 76, with the
control at **zero**, because no flag `rg` has crosses that gap. `refs`
on a plain symbol is the opposite — 124 to grep's 236 — so ask it about
settings and history, not about names you already know.

The number an agent should care about most: of those 204 questions,
`ripgrep` returned **more than twenty files for 97 of them**, median
seventy. Those are the questions where a ranked answer is the difference
between reading three files and reading seventy — and they are nearly
half of what real people ask. The local default turns 40 of those 97
into a top-ten answer.

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
