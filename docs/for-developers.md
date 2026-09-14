# wsindex, for the developer deciding whether to install it

## What the thing is

You point it at the several git repositories you actually work in. It
reads them, cuts every file along its syntax tree — functions, classes,
config sections, document headings — turns each piece into a vector, and
keeps the lot in a file next to the config. Then you ask questions and it
gives you `file:line`.

By default that all happens on your machine. The model runs in your
process, the index is a file you can delete, and a warm search opens zero
sockets. There is no account and no server to run.

**What that default costs you is measured, and you should know it before
you install anything.** On 154 questions taken from the issue trackers of
the projects being indexed — real questions, in the words of people who
had never heard of this tool — the fully local default puts the right
file in the top ten 65 times. `ripgrep` manages 60. That is a tie with
grep — inside noise — and nobody installs a tool to tie with grep.

What changes it:

| What you turn on      | Finds it (of 154) | What leaves your machine |
| --------------------- | ----------------: | ------------------------ |
| nothing — the default |                65 | nothing                  |
| hybrid turned off     |                55 | nothing                  |
| a hosted reranker     |                85 | the query and ~40 chunks |
| a hosted embedder too |               109 | every chunk, once        |

Fusing a lexical pass with the vector one is what took the default to 65
from the 55 it used to manage; it is free, local and on. The hosted
reranker sends the query and about forty candidate chunks per search —
not your repository — and it is the line where this stops tying with grep
and starts beating it 85 to 60.

**What it saves, measured:** on 204 tasks drawn from the indexed
projects' own issue trackers, reaching the answer took a median of
**1 045 tokens of reading against grep's 9 449**, and less reading in 85
of the 99 tasks both finished. That is the size of the pile each tool
puts in front of you, counted the same way on both sides.

**Two things here beat `grep` outright, and they are not the search.**
Asking *why* a definition looks the way it does — walking its lines back
to the commit that explains them — named a commit that really touched
those lines 161 times of 164, where `git log -S` managed 146. And
reaching a setting written `max_retries` in a yaml from the
`MaxRetries` in the code that reads it: 64 of 76, with `rg` scoring
**zero**, because no flag it has crosses that gap.

The mirror of that, said plainly because you will otherwise assume it:
asking `refs` where an ordinary symbol is defined **loses** to `rg -w`,
124 to 236.
If you already know the exact name, grep is the better tool and this one
has nothing to add.

What follows is what it is measured to do — see
[field-trial.md](field-trial.md) for how that was measured and what else
it found.

## What it gives you today

**Finding the right file in a codebase too big to grep.** This is the
real win and it grows with the codebase. On DBeaver — 11 786 files,
125 000 chunks — wsindex put the right file in the top three for four out
of four identifier questions. `ripgrep` found one of the four and buried
two more in lists of over twenty files. That is the case you already know:
you grep a name, you get two hundred hits, and you start reading.

**One question, several repositories.** Searching six repos at once
without remembering which one holds what is not a trick, it is just what
the tool does. If your docs live in one repo and the code in another, both
answer.

**Knowing why a file is missing.** `wsindex explain path/to/file` tells
you whether it was indexed, as what, and if not, which rule left it out.
In the trial it was asked about 240 files and answered correctly every
time. Use it the moment anything looks wrong.

**Re-indexing that costs nothing.** Running `wsindex index` again after
no changes takes under a second and does not get slower as the corpus
grows — 0.68 s on the 125 000-chunk workspace. You can put it in a hook
and forget it.

## What it does not give you yet

**Asking in plain English does not work with the default model.** The
trial asked questions phrased the way a person thinks — *"is there logic
that skips the wipe when nothing changed since last time"* — deliberately
using none of the words in the answer file. The default put 2 of 23 in
the top three.

`ripgrep` found **none** of them, so the questions are fair and the need
is real. And the limit turns out to be the model rather than the tool:
the same chunks and the same pipeline, with a frontier code embedder and
reranker, answer **12 of 23 in the top three and 18 of 23 in the top
ten**. What you install runs a 23M-parameter model on your own machine
and sends nothing anywhere, which is the trade — not a ceiling on what
this is capable of.

**A deeper list still pays.** History no longer floods the results —
commit messages are capped at a fifth of any list, which is what took
descriptive answers from 0 to 4 of 30 and identifier answers from 3 to 5
in the top three. What the cap cannot do is make the list longer, and a
fifth of the answers sit at ranks 10 to 50. Searching with

```console
$ wsindex search "your question" -k 50 --kind code --kind doc
```

still finds roughly a third of the descriptive answers against the
default's one in seven. Worth the habit.

**There is a second model, and it is a trade.** `CodeRankEmbed` lifts
identifier answers from 9 of 20 to 13, and from 1 to 4 at rank one — and
drops descriptive from 4 to 2. If what you do is find where things live,
it is the better choice; see the README for the four config lines it
needs and the reasons each one exists.

**If your language is not in the table, you get an empty index and no
warning.** Elixir and Scala have no entry, so those files are not chunked
as text — they are skipped. One workspace indexed 30 files out of 417 and
`wsindex index` said only `files: 30`. Check with `wsindex explain` on any
source file before you trust an index; if it says *no language claims this
suffix*, add a `formats` entry for the repo and re-index.

**Two crashes used to be waiting in real repositories, and are fixed.**
A repository with more than about 17 900 files ended the run with
`OverflowError`; a single commit message carrying a non-UTF-8 byte — a
name like *Würkner* written in 1996 — ended it with
`UnicodeEncodeError`. Three of the twenty trial workspaces hit one of
them. Both now have a test pinning the exact mechanism, and an index run
that skips a whole language says so instead of reporting `files: 30`.

## Is it worth your twenty minutes

**Yes, if** you work across several repositories at once, at least one of
them is large, and you spend real time looking for where something lives.
Install it, index, and use `-k 50 --kind code`. It will save you the
two-hundred-hit grep.

**Not out of the box, if** what you wanted was to ask questions in
words. The default answers 2 of 23 of those. The design answers 12 with a
frontier model, so this is a setting away rather than a rewrite — but it
is not what you get by typing `wsindex init`.

**No, if** your workspace is Elixir, Scala, Swift or Objective-C and you
do not want to hand-write a `formats` table first.

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
