# thulr for agents, and for the person wiring one up

## Read this before you wire anything up

**Nine measurements say a coding agent that has the repositories on disk
gets nothing from these tools.** Not "we could not show it" — nine
designs, most of them aimed at the previous one's excuse:

| what was tried                                        |                                  result |
| ----------------------------------------------------- | --------------------------------------: |
| 24 real issues, local and hosted arms                 | same lines, 19 of 24 dearer, p = 0.0066 |
| the whole organisation indexed, repo not named        |                19 / 19 / 18 lines of 24 |
| the answer handed over in the task, no MCP at all     |               8 of 24 cheaper, p = 0.15 |
| the largest workspace in the corpus                   |                           no difference |
| 75 tasks **selected because ripgrep drowned on them** |          ruined 16 against 13, p = 0.65 |
| 15 renames across a spelling boundary, with a skill   |                  8, 8 and 9 sites of 27 |
| 26 "where does this live", local embedder             |    15 answered against the control's 16 |
| the same 26, hosted embedder                          |                           16 against 16 |
| the same 26 with the shell taken away                 |                           13 against 13 |

The first six asked the agent to *fix* something. The last three asked
only where code lives, which is the question these tools were built for
and the one where a wrong answer cannot be recovered by working harder.
The ninth took `Bash` and `Grep` away and left `Read` and `Glob`, the
policy some harnesses actually run: losing the shell cost the control
three answers and cost the thulr arm the same three.

**It is not a retrieval failure, and that is the useful part.** The agent
called these tools in every single run of the last three. They put the
right file in front of it 69% of the time on the local embedder, 81%
hosted, and 96% once grep was gone. What never moved was the answer —
because an agent that can open files reaches them anyway. In the hosted
run the tool delivered the truth file 21 times and the control found
that same file unaided in 14 of those 21.

Retrieval was not what the agent was short of. Neither was information
in general: handing the answer over inside the task, at 125 tokens
instead of 2 200, changed nothing either. That closes the whole family of
fixes — a better transport, a skill, delegation, a model inside the tool.

## Who these tools are for, then

**An agent that cannot open a file.** No filesystem, no git: a chat
client, a bot on another machine, a sandbox with the index mounted and
nothing else. There the control is not grep, it is zero, and this server
is the only way in. That case cannot be measured against an alternative
because it has none — but it has a number that governs it, and it is not
the one quoted for search.

Everywhere else the job of a hit is to *point*: the reply says
`file:line` and the agent opens it. For a caller with no files the reply
*is* the answer, so what matters is whether the lines that matter came
back inside it. Asked on 135 harvested questions that have line-level
truth — does the returned text contain the lines the fix changed:

| hits asked for | hosted embedder | local embedder | median lines in the reply |
| -------------- | --------------: | -------------: | ------------------------: |
| k = 10         |              74 |             44 |                 515 / 261 |
| k = 20         |          **92** |         **57** |                 956 / 509 |
| k = 30         |              98 |             66 |               1 371 / 720 |

Which is why `k` defaults to **20** here. Past twenty the hosted model
buys an answer per 69 lines of context where the step to twenty bought
one per 24.

The CLI settled on twenty as well, separately and for a different
reason — a person's cost is rows on a terminal, not context — so the two
agreeing is a coincidence rather than a rule, and neither should be
changed because the other was.

Returning *more* around each hit instead — the enclosing neighbourhood,
which the server can do since it has the file even when the caller does
not — was measured and is the worse lever. Widening a k=10 reply by a
hundred lines each side reaches 84 answers for 1 673 lines; asking for
thirty hits reaches 98 for 1 371. More hits beat fatter hits at every
budget on both models.

## The three tools

```
search(query, k=20, repo=, lang=, kind=, path=, symbol=, budget=)
refs(name)     — which config declares a setting and what names it in
                 code, across spellings (max_retries = MaxRetries), which
                 is the half that beats grep; also where a symbol is
                 defined and what names it, which does not
why(symbol)    — the commits that wrote a definition, and their messages
```

Every answer carries `file:line` and the chunk text.

**`search` may ask more than once.** With `[rewrite]` configured the
question is also put in the words the code is likely to use and the lists
are fused — worth +25 answers of 355 on the hosted configuration and +20
on the local one. It is off by default and costs a model call per search.
Nothing about the reply shape changes, so a client need not know; the
latency does.

An agent that already reformulates its own queries gains less from this
than a person does, and that is not a guess — it is the mechanism the
nine measurements above found. If your client rewrites questions itself,
leave `[rewrite]` off and save the call.

**And depth is a substitute for it.** The gain was measured at `k=10`.
At `k=30` the same corpus answers 267 as typed and 272 rewritten, which
is five and not significant — while raising `k` alone is worth +75. This
surface already defaults to twenty, so a caller here starts most of the
way to where rewriting would have taken it, and pays nothing per search
to be there.

**`budget` caps the answer in tokens, which `k` cannot.** Ten hits are
anywhere between four hundred tokens and eight thousand depending on what
they are, and an agent filling a context window cannot spend "ten hits".
Given a budget, the reply carries `tokens` actually spent and
`dropped_for_budget`, so the agent knows it was cut rather than knowing
nothing. It is the right knob now that `k` defaults higher: cap the
tokens and let the tail of the ranking go, rather than ask for fewer hits
and get the same narrow slices of the same few files.

**`unsearched` names repositories that were never indexed.** An agent
reporting "there is no such code" about a workspace half of which was
never read is worse than an agent saying it does not know — and a caller
with no filesystem cannot discover the gap any other way. Every reply
carries this list, empty or not.

Both are in the reply shape, not in prose somewhere: an agent does not
read a README.

## What the ranking actually is

These are facts about search, and they stand. They are not savings for an
agent; see above.

Right file in the top ten, on 204 questions taken from the indexed
projects' own issue trackers — nobody here wrote them: the local default
**98**, ripgrep **71**, with a hosted reranker **109**, and with a hosted
embedder as well **132**. In the top *three* it is 62 against ripgrep's
71, which is noise: the win is at depth, not at the very top.

**Two answers here beat `grep` outright.** `why` — a definition to the
commits that wrote it — named a commit that really touched those lines
199 times of 202, against `git log -S` at 174, winning the discordant
pairs 16 to 1. And `refs` reaching a setting spelled one way in a config
and another in code: 64 of 76, with the control at **zero**, because no
flag `rg` has crosses that gap. `refs` on a plain symbol is level and a
little behind — 268 to grep's 275 — so ask it about settings and history,
not about names you already know.

Note what `refs` bridges, because the agent runs explain themselves by
it: a mechanical transform, `max_retries` to `MaxRetries`, `thin-vec` to
`thin_vec`. A language model performs that transform for free, which is
why handing it to an agent changed nothing. It does not bridge
`oauth_client_id` to `clientId`, and neither does anything else here.

**Reaching the answer costs about a tenth of the reading** — for a fixed
reading policy, not for a model. Over the same 204 tasks, `grep` read a
window around every match the way `rg -C` shows it, thulr read the line
ranges it ranked, and both stopped when a file holding the answer was in
front of them: 125 tasks found against 112, median 1 263 tokens against
13 474, cheaper on 89 of the 102 both found. This measures the size of
the pile each tool puts on the desk, which is the part the tool controls.
An agent that skims, gives up on a file after two lines and rewrites its
query does better with either — which is exactly what the nine runs above
found.

Of those 204 questions `ripgrep` returned more than twenty files for 97,
median seventy, and the local default turns 40 of those 97 into a
top-ten answer. That is a real advantage and it belongs to the person at
the keyboard who asks once. The fifth measurement above selected its
tasks by precisely that failure and found no agent-side difference, so do
not read it as wiring advice.

## What it costs you

The search itself is free and local: no API, no key, no tokens. What
costs tokens is the answer arriving in your agent's context, and that is
the number `budget` exists to control.

Indexing costs minutes once (a 2 000-file repository in 37 seconds,
11 800 files in four minutes) and under a second per re-index after,
whatever the corpus size. Nothing leaves the machine unless you
explicitly configure a remote model — see [for-security.md](for-security.md).

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
    "thulr": { "command": "thulr", "args": ["mcp"] }
  }
}
```

The server reads the workspace config the same way the CLI does, so
whatever `thulr status` shows is what the agent will search.
