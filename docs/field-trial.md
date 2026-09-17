# Field trial — twenty real workspaces

wsindex had never been run on a codebase that was not its own. This is
what happened when it was: twenty organizations from GitHub, 105
repositories, 4.4 GB of working trees and full history, and 204 questions
written down **before** wsindex was allowed to run.

It is not a demonstration. Three workspaces are in because wsindex has no
grammar for their language, and every search result has a `ripgrep`
control, because a question `grep` already answers is not a question that
needs an index.

The corpus was selected from the GitHub API rather than from memory:
506 organizations collected by searching twelve languages across two
star bands, 394 with three or more live repositories, twenty chosen
against size, age, repo count and language coverage. The harness, the
frozen questions and every raw measurement live under `probes/`, which
this repository does not track — review artifacts stay out of git. What
is reproducible from here is the method below.

## How the questions were made honest

A tester opened each workspace with `Read`, `Glob`, `Grep` and `git log`
only — **never wsindex** — and wrote twelve questions a developer joining
that codebase would ask, together with the true answer (`file:line`) found
by reading. Those files were written to disk and not edited afterwards.

Twelve per workspace, in three classes:

- **Literal** (4) — the words of the question are in the code.
- **Descriptive** (6) — the behaviour described in words that do *not*
  appear in the answer file. Mechanically checked: every word of four or
  more letters, minus function words, must be absent from the whole file
  **as a substring**. Roughly forty candidate questions were discarded
  for failing this.
- **Cross-repo** (2) — the answer is in a different repository from the
  one a person would open first.

The ordering is the whole point. It is very easy to look at what an index
returned and decide that was the question; every wrong conclusion in this
project's history came from grading an answer against a question chosen
after seeing it.

## Does it index?

|                                            | Workspaces |
| ------------------------------------------ | ---------: |
| Indexed properly (94–107% of source files) |     **14** |
| Indexed almost nothing, silently           |      **3** |
| Crashed outright                           |      **3** |

Where it works, it works well and it is fast. Throughput held at roughly
700–900 chunks per second across two orders of magnitude of corpus size.
The largest workspace that finished — dbeaver, 11 786 files — took 258
seconds and 349 MB for 125 353 chunks.

Re-indexing is the quiet triumph. **Re-running an unchanged workspace
costs 0.35–0.89 seconds and does not grow with corpus size**: dbeaver,
with 125 353 chunks, comes back in 0.68 s. That is the claim the README
makes and it survives contact with strangers' repositories.

One incremental number does not survive. The README's **0.24 s for a
single changed file** was not reached on any of the seventeen workspaces;
the range measured was **2.53–4.16 s**, including on an idle machine. The
difference from the unchanged case is the embedding model, which has to
be loaded before one chunk can be embedded.

### Three crashes, both mechanisms exact

**`OverflowError: timeout is too large`** — `ingest/commits.py` passes
`timeout=GIT_TIMEOUT * len(rel_paths)` to a subprocess. With
`GIT_TIMEOUT = 120.0` and Python's `poll()` capped at 2³¹−1 milliseconds,
**any repository with more than 17 896 files to blame ends the whole
run**. Hit by syncthing (`docs-pre-rendered`, 33 048 files) and
LadybirdBrowser (`ladybird`, 19 253 source files). The second was
predicted from the first before it was run, and came true.

**`UnicodeEncodeError: surrogates not allowed`** — `read_commits`
decodes git's output with surrogate escapes, so a commit message
containing a non-UTF-8 byte yields a lone surrogate; `Chunk.chunk_id`
then calls `text.encode("utf-8")` and raises. **Six of FreeType's 8 545
commit messages** carry one — Latin-1 names written between 2000 and
2005: Céline, Würkner, Syrjälä, Domröse. Six messages out of eight and a
half thousand stop the indexing of a whole workspace.

Neither is a degraded index. Both are a traceback and an empty store.

### Three silences, which are worse

`pow-auth` indexed **30 of 417 files**. `circe` indexed 67 of 455.
`phoenixframework`, 286 of 892. Their languages — Elixir and Scala — had
no entry in the language table, so their files were not chunked as text,
they were **skipped entirely**. Elixir has a grammar now, and the fifty
unreachable questions below are what bought it; Scala still does not.

The cure is three lines of `[repos.formats]` config, and `wsindex explain <path>` says exactly that when asked. But `wsindex index` printed
`files: 30` and nothing else, and `wsindex status` showed three healthy
repositories. wsindex warns loudly when a grammar *partly* fails to read
one file. It says nothing at all when it skips 93% of a workspace.

For those three, the resulting index is 88%, 96% and 80% commit messages,
and `search --kind code` answers `no results`.

## Does search work?

204 questions, 17 workspaces. Each cell counts answers found at all —
**default** is `wsindex search -k 10`, **best** is `-k 50 --kind code --kind doc`, **ripgrep** is `rg -l` returning twenty files or fewer.

| Class           | Questions | Default |   Best | ripgrep                            |
| --------------- | --------: | ------: | -----: | ---------------------------------- |
| Literal         |        68 |      34 |     46 | **56** found, 10 drowned, 2 missed |
| **Descriptive** |       102 |   **5** | **28** | **0** found, 1 drowned, 101 missed |
| Cross-repo      |        34 |       9 |     14 | 15 found, 7 drowned, 12 missed     |

Read the descriptive row twice. **ripgrep found none of them** — so the
questions are real, and the need for something other than grep is real.
And wsindex, by default, found five.

### Asked again, a pipeline later

That table is the state of things on 2026-09-11, with `all-MiniLM-L6-v2`
and the defaults of the day. The retrieval width, the lexical arm of the
fusion, the reranker and a hosted embedder all arrived after it, so the
same questions were put again — the 84 authored questions of the seven
workspaces this repository keeps, top ten, nothing re-written:

| Class           | Questions | ships (MiniLM) | `voyage-code-4` + `rerank-2.5` | ripgrep |
| --------------- | --------: | -------------: | -----------------------------: | ------: |
| literal         |        28 |             23 |                         **28** |      21 |
| **descriptive** |        42 |          **1** |                         **21** |   **0** |
| cross-repo      |        14 |              6 |                         **12** |       6 |
| all             |        84 |             30 |                         **61** |      27 |

Paired, the hosted configuration answers 32 questions the local one
misses and misses one it answers, p < 0.000001. On the descriptive class
it reaches **hit@10 = 0.51** of 41 reachable, which is the line the plan
of 2026-09-11 set in advance — passed by one question, with no margin.

Two things changed and one did not. What changed: the crossing from a
developer's English to the code's vocabulary, diagnosed below as a
property of the model, is a property of the model — swapping it moved the
descriptive class from 1 to 21 with nothing else touched. And the
cross-repo row reversed, from level with `ripgrep` to 12 against 6.

What did not change: **the model that ships still answers 1 of 42.** The
configuration that meets the need is the one that sends every chunk to a
hosted embedder. The local mode is not a slightly weaker version of it on
this class; it is a different capability.

### The index is not the problem

Handed a line taken verbatim out of the answer file, the index returns
that file **first** in 44 of 48 cases across four workspaces. Storage,
chunking, embedding and search are all sound. What fails is the crossing
from a developer's plain English to the code's vocabulary, and that is a
property of `all-MiniLM-L6-v2`, a general-purpose sentence model with a
256-token window.

### The defaults hide what there is

Descriptive answers found: **5 at `-k 10`, 28 at `-k 50 --kind code --kind doc`**. A fifth of the class is reachable and is not being
reached, because it sits at ranks 10–50 behind commit messages.

Commit chunks are between 8% and 96% of an index. On `DatabaseCleaner`,
27 of 36 top-three slots went to commit messages; on `circe`, 31 of 36.
Asked about a named constant in a Rust repository, the top ten hits were
all commits, with scores within 0.005 of each other.

The re-ranker is built for exactly this and cannot reach it: measured on
one workspace, it lifted an answer from rank 6 to rank 1 and another from
14 to 8, but the answers sitting at 17, 22 and 46 were never in its
candidate pool.

### Where it already beats grep

On the two largest workspaces that indexed, ripgrep starts drowning and
ranking starts paying:

- **dbeaver** (125 353 chunks): wsindex put **4 of 4** literal answers in
  the top three. ripgrep found one, drowned on two.
- **icsharpcode** (78 440 chunks): wsindex 3 of 4 in the top ten by
  default, 4 of 4 configured. ripgrep found one, drowned on three.

This is the shape of the real case: the bigger the codebase, the less a
flat list of matches is worth.

## The analysis commands

`domains` ran 193 times across the corpus. **151 of those runs reported
"too few to have domains. Index first," while a complete index sat
beside them** — the default `--prefix src/` is this project's own layout,
and a Ruby gem keeps code in `lib/`, a Go module at the root, a Java
project under `src/main/java`. Given the right prefix it works: 42 runs
reported real package counts.

`dupes` found pairs in 47 repositories and nothing above the threshold in
42\. It is scoped to one repository at a time, so on the workspace chosen
*because* its three adapter gems are near-copies of each other, it cannot
see the duplication at all.

`refs` found nothing for either port probe in any of 29 attempts, which
matches what the project already measured: the link vocabulary is thin.

`explain` was the best-behaved command in the trial. Asked about 240
sampled files it gave a correct and specific answer every time, including
the three workspaces where it was the only thing that could have told a
user what had gone wrong.

## The verdict, against the rule declared in advance

The rule was written before the run: **works** if the cold index
completes and its warnings are true; **needed** if descriptive `hit@3 ≥ 0.6` while the control finds the answer in no more than 30% of the same
questions.

**Works: 14 of 20.** Three crashed, three said nothing while indexing
almost nothing.

**Needed: the need is proven, the answer is not delivered.** The control
found **0 of 102** descriptive answers, so the questions developers
cannot grep are real and common. wsindex placed **1 of 102** in the top
three. That is the cell of the table marked *fails at its own job* — and
it fails at a job that genuinely needs doing.

The machinery under it is not what fails. An index that returns the right
file first for 92% of verbatim queries, re-indexes 125 000 chunks in
0.68 s, and beats grep outright on the largest codebase in the corpus is
a working engine with the wrong model in it, a candidate pool too
shallow, and history drowning the code.

## Questions this project did not write

Everything above rests on questions written by the person who built the
tool. Every guard around them — freezing them before a run, the
substring leak rule, the ripgrep control — narrows that and none of it
removes it, and one sentence from a sceptic ends the argument.

So they were replaced at the source. `scripts/harvest.py` takes a closed
issue's title as the question, in its author's words, and the files the
pull request that closed it changed as the answer. Neither end was
produced by anybody measuring this. The selection rules are frozen in
code: merged before the pinned commit so the answer is in the indexed
tree, an explicit `fixes #n` so the pairing is the author's claim, one to
five files that all still exist at the pin, no test-only or doc-only
fixes, no bots, and the same substring leak rule. Every question carries
the issue and pull request urls. 355 across the seven workspaces, 204 in
the routine tier.

The control was rebuilt too, because swapping the questions while
keeping a hand-written `rg_query` would have been a swindle: terms are
extracted from the question by a frozen rule, all of them are tried, and
ripgrep's *best* outcome is the one reported.

Fifty of the 204 used to be unreachable — the file was never indexed,
every one of them Elixir, which had no grammar here. They are reachable
now, and the ratio was itself the finding that bought the grammar: real
questions land where the codebase is, not where the indexer is
comfortable. All 204, paired, McNemar exact:

| Configuration             | hit@1 | hit@3 | hit@10 |
| ------------------------- | ----: | ----: | -----: |
| default — hybrid on       |    36 |    62 |     98 |
| hybrid turned off         |     1 |    35 |     72 |
| + a hosted reranker       |    31 |    68 |    109 |
| a hosted embedder as well |    56 |    99 |    132 |
| `ripgrep`                 |     — |     — |     71 |

**The two depths disagree, and both belong on the page.** At ten the
default beats ripgrep 98 to 71 — 48 questions only it answers against 21
only ripgrep answers, p = 0.0016. At three it does not: 62 to 71,
p = 0.28, which is noise and not a win for either. Knowing the exact
identifier is still grep's case, and it always was.

Read the hybrid row twice. Switching fusion off costs 26 answers at
depth ten and takes hit@1 from 36 to **1 question in 204** — commit
messages score well against any prose and take the first slot, and the
lexical arm is the only thing that dislodges them. It is free, local and
on.

The bucket that matters most is where ripgrep drowned: it returned more
than twenty files for **97 of the 204**, median seventy. The local
default turns 40 of those into a top-ten answer. That is the half of
real questions where ranking is the entire value.

Two numbers here came from a measurement that had to be repaired before
it could be believed. The earlier version of this table put the default
at 65 and ripgrep at 60 and called it a tie. The 65 was real for the
retrieval of the time; the 60 was not reproducible, because the corpus
is pinned by sha and the threshold is a constant but the control binary
was pinned by nothing. Rebuilt on ripgrep 15.2.0 the control answers 71,
so the honest reading of that day is that the default was *behind* the
control, not level with it. The report prints its ripgrep version now.

## How it is checked now

The trial above was a one-off: a tester, a fortnight, and a document.
What replaced it is three instruments in the repository, because a
measurement nobody can re-run is a story.

They are kept apart on purpose, and `docs/design/test-methodology.md`
says why at length. A result from one says nothing about the next.

- **Tier 1** (`scripts/tier1.py`) drives the shipped binary over the
  pinned corpus and checks the *claims*: that a cited `file:line` exists,
  that a run reporting success read the repository, that an index answers
  the same after compaction, that re-indexing an unchanged tree changes
  nothing. Fifteen checks across seven workspaces.
- **Tier 2** (`scripts/tier2.py`) asks whether the answer is right, with
  ground truth that exists independently of the tool — `git log -L` for
  `why`, a four-spelling search for `refs` — and a control that is what
  somebody would type instead.
- **Tier 3** (`scripts/tier3.py`) asks whether any of it saves work: two
  workers, one token budget, the same tasks, counted on what each has to
  read before the answer is in front of them.

Each writes a protocol into `docs/protocols/`, generated rather than
typed, and not edited afterwards.

What they found on their first real runs is the argument for having
them. Tier 1 caught a 690-second no-op — an unchanged re-index of an
11 786-file workspace taking 762 seconds against a documented promise of
under a second — which had shipped that morning, survived 1 116 green
unit tests, and is invisible on six of the seven workspaces. Tier 2 put
the first number on `why` (199 of 202) and showed that `refs` on an
ordinary symbol *loses* to `rg -w`. Tier 3 answered the question this
project had never been able to answer.

And they were wrong before they were right: tier 2's harness lied four
ways and the methodology twice more, tier 3's accounting flattered its
own tool by a factor of four hundred. Each was caught by a number
disagreeing with the mechanism rather than by anything failing, which is
why the order — run, check the method, *then* read the results — is
written down as a rule.

## What happened next, and it changes the verdict above

That paragraph was written as a consolation and turned out to be the
finding. Everything it names was fixed or tested afterwards, and the last
of them settled the question this document could not.

History was capped at a fifth of a result list; chunks were given their
own name and place to be embedded with; `domains` and `dupes` were made
to read a workspace rather than one project's layout and one repository;
the two crashes and the silent skipping were fixed with tests that pin
the mechanism. The questions here became a permanent instrument, `poe relevance`, with the ripgrep control and a pinned corpus, running in CI.

The thin link vocabulary was diagnosed rather than accepted. `refs` found
nothing in 29 attempts because the extractor had never read the name the
syntax tree already put on every chunk — the vocabulary was whatever four
regular expressions caught, and nothing else. Reading it gives caddyserver
1 090 names with a definition in one file and a mention in another, where
five workspaces had previously produced three.

Then the model was replaced. **Same chunks, same questions, same
pipeline**: the plain-English class goes from 2 to **12 of 23 in the top
three** and 5 to **18 of 23 in the top ten**, and identifier questions to
16 of 16 — every one that is reachable. The gate this trial declared in
advance, descriptive hit@10 of 0.50, is cleared at 0.78.

So the verdict stands as a description of what shipped on the day, and
must not be read as a description of the design. The promise was not
unachievable. It was locked behind a 23M-parameter model chosen to keep
everything on one laptop, and every part of the system underneath it was
sound. What is still true: that trade is a real one, and nothing in this
repository sends your code anywhere by default.
