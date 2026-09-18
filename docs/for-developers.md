# wsindex, for the developer deciding whether to install it

## The one thing worth knowing first

**There is a class of question about unfamiliar code that `grep` does not
answer badly — it answers zero.** A tester wrote 42 of them as what a
developer joining that codebase would ask, before wsindex was allowed to
run, and every word of four letters or more from the question was
mechanically checked absent from the answer file. *"Is there logic that
skips the wipe when nothing changed since last time?"*

`ripgrep` found none of them. That is its own score, not our claim, and
it is roughly half of what people actually ask about code they do not
know.

wsindex answers **21 of the 42** in the top ten, 14 in the top three, 7
first — with a hosted embedder. With the model that ships, **1**.

Read that pair together, because it is the whole decision. The
capability that makes this tool worth installing is the one that needs a
hosted model; the fully local default is good at the questions grep is
also good at.

## What the thing is

You point it at the several git repositories you actually work in. It
reads them, cuts every file along its syntax tree — functions, classes,
config sections, document headings — turns each piece into a vector, and
keeps the lot in a file next to the config. Then you ask questions and it
gives you `file:line`.

By default that all happens on your machine. The model runs in your
process, the index is a file you can delete, and a warm search opens zero
sockets. There is no account and no server to run.

## What the local default does and does not buy

On 204 questions taken from the issue trackers of the projects being
indexed — real questions, in the words of people who had never heard of
this tool — the fully local default puts the right file in the top ten 98
times. `ripgrep` manages 71. Paired, that is 48 questions only wsindex
answers against 21 only ripgrep answers, p = 0.0016.

**Read the other depth before you get excited.** In the top *three* the
default manages 62 and `ripgrep` 71, and that difference is noise
(p = 0.28). If you know the identifier you are looking for, grep is
still the faster way to put it on screen. What this is for is the
other case: `ripgrep` returned more than twenty files for 97 of the 204,
median seventy, and the default turns 40 of those into a top-ten answer.

What changes it:

| What you turn on      | Finds it (of 204) | What leaves your machine |
| --------------------- | ----------------: | ------------------------ |
| nothing — the default |                98 | nothing                  |
| hybrid turned off     |                72 | nothing                  |
| a hosted reranker     |               109 | the query and ~40 chunks |
| a hosted embedder too |               132 | every chunk, once        |

Fusing a lexical pass with the vector one is free, local and on, and it
is what holds the top of that list: switched off, the right file is
*first* for 1 question of 204 instead of 36, because commit messages
score well against any prose and take the slot. The hosted reranker
sends the query and about forty candidate chunks per search — not your
repository — for another 11 answers.

**What it saves, measured:** on 204 tasks drawn from the indexed
projects' own issue trackers, reaching the answer took a median of
**1 263 tokens of reading against grep's 13 474**, and less reading in 89
of the 102 tasks both finished. That is the size of the pile each tool
puts in front of you, counted the same way on both sides.

## Two things beat `grep` outright, and they are not the search

Asking *why* a definition looks the way it does — walking its lines back
to the commit that explains them — named a commit that really touched
those lines 199 times of 202, where `git log -S` managed 174, winning the
discordant pairs 16 to 1.

And reaching a setting written `max_retries` in a yaml from the
`MaxRetries` in the code that reads it: 64 of 76, with `rg` scoring
**zero**, because no flag it has crosses that gap. This is a correctness
argument rather than a speed one — you grep the spelling you were given,
edit what you find, and nothing tells you the job is half done.

Neither of these uses a vector at all. They are exact walks over a link
graph, they need no model, and they are the same on every configuration.

The mirror of that, said plainly because you will otherwise assume it:
asking `refs` where an ordinary symbol is defined is **level** with
`rg -w` and slightly behind it, 268 to 275 of 280. If you already know
the exact name, grep is still the better tool.

## What it gives you today

**The question you cannot grep.** See the top of this page. This is the
only thing here with no alternative, and it is the reason to install.

**Finding the right file in a codebase too big to grep.** On DBeaver —
11 786 files, 125 000 chunks — wsindex put the right file in the top three
for four out of four identifier questions. `ripgrep` found one of the four
and buried two more in lists of over twenty files.

**One question, several repositories.** On 14 questions whose answer is
in a different repository from the one you would open first, wsindex
found 12 and `ripgrep` 6. Searching six repos at once without remembering
which one holds what is not a trick, it is just what the tool does.

**Knowing why a file is missing.** `wsindex explain path/to/file` tells
you whether it was indexed, as what, and if not, which rule left it out.
In the field trial it was asked about 240 files and answered correctly
every time. Use it the moment anything looks wrong.

**Re-indexing that costs nothing.** Running `wsindex index` again after
no changes takes under a second and does not get slower as the corpus
grows — 0.68 s on the 125 000-chunk workspace. You can put it in a hook
and forget it.

## What it does not give you

**Plain English does not work on the default model.** 1 of 42 in the top
ten, against 21 with a hosted embedder and reranker. The same chunks, the
same pipeline, the same funnel: what changes is the model, and the limit
is not something the design closes.

Four local models were measured against the shipped one on the 204
harvested questions — a general model five times larger, two trained on
code, and the 23M default. The default wins both axes: right file 97, and
a chunk that holds the answer 44 of 135, against 93/41, 91/40 and 85/36.
The code-specific one did *worse*. So do not bother swapping it; this
ceiling is not one a local model closes.

**Nothing for a coding agent.** Nine measurements say an agent that has
the repositories on disk gains nothing from these tools over MCP,
including three that asked only where code lives and one that took the
shell away. See [for-agents.md](for-agents.md) for the numbers and the
mechanism.

**A deeper list still pays, and it is a trade rather than a free win.**
The default holds the answer for 98 of the 204, and

```console
$ wsindex search "your question" -k 50 --kind code --kind doc
```

holds it for **145**. Worth the habit, and worth knowing what it costs —
an answer at `-k 10` is about 2 200 tokens to read, and five times that
at `-k 50`.

The depth is doing most of the work there, not the filter: at depth ten,
restricting to code and docs scores 77 against the unrestricted 79. But
the filter is not nothing either — commit messages take 39 of the 252
top-three slots on the hosted configuration, and two descriptive answers
sit at rank 3 and 8 once they are filtered out.

**If your language is not in the table, you get an empty index and no
warning.** Thirty-three languages and formats are claimed now, including
the three that used to be the reason not to install — Scala, Swift and
Objective-C — plus Elixir, SQL, HCL, shell and the config formats. If
yours is not among them its files are skipped rather than chunked as
text. Check with `wsindex explain` on any source file before you trust an
index; if it says *no language claims this suffix*, add a `formats` entry
for the repo and re-index.

**Two crashes used to be waiting in real repositories, and are fixed.**
A repository with more than about 17 900 files ended the run with
`OverflowError`; a single commit message carrying a non-UTF-8 byte — a
name like *Würkner* written in 1996 — ended it with `UnicodeEncodeError`.
Three of the twenty trial workspaces hit one of them. Both now have a
test pinning the exact mechanism, and an index run that skips a whole
language says so instead of reporting `files: 30`.

## Is it worth your twenty minutes

**Yes, if** you regularly arrive in code you did not write and ask about
behaviour rather than names — and you are willing to configure a hosted
embedder. That is the 21-of-42 case, and grep's score on it is zero.

**Yes, locally, if** you work across several repositories at once, at
least one of them is large, and you spend real time looking for where
something lives. It will save you the two-hundred-hit grep, and nothing
leaves your machine.

**No, if** what you wanted was to ask questions in words *and* keep
everything on your own machine. Those are not the same configuration
today, and pretending otherwise would waste your evening.

**No, if** you already know the identifier. Use grep.

## Starting

```console
$ wsindex init myworkspace
$ wsindex add-repo api ~/checkouts/api
$ wsindex add-repo docs ~/checkouts/docs
$ wsindex index
$ wsindex search "retry backoff" -k 50 --kind code
```

`wsindex shell` keeps the model loaded between questions, which is worth
it after the second search — a cold search pays about two seconds to load
the model, and that is most of what you wait for.

`wsindex status` shows what is indexed and at which commit. `wsindex explain <path>` is the first thing to run when an answer looks wrong.

See [field-trial.md](field-trial.md) for how all of this was measured and
what else it found.
