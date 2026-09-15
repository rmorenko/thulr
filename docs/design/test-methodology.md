# Test methodology

How this project decides whether it works, written down before the next
run rather than after it.

It exists because of a specific failure, twice in one day. Hybrid
retrieval was turned on and the reranker's candidate selection silently
started throwing the lexical arm away: top-three fell from 50 to 32.
Then the lexical arm was rescored for a tidier display and quietly
reordered itself by semantic similarity: top-ten fell from 85 to 77.
**Both times 1116 unit tests passed.** A suite that proves the mechanism
runs cannot see quality leave the building, and every number in this
repository's documents is a quality number.

## The three questions, and why they are different

Everything below sorts into three questions that need different
instruments. Conflating them is how `acceptance.py` certified 10/10
against a failure the field trial then found in 203 of 204 questions.

1. **Does it run?** Given a workspace, does the command finish, and is
   what it reports true of that workspace. Cheap, deterministic, belongs
   in CI.
1. **Is the answer right?** Given a question with a known answer, does
   the command produce it, and does it beat the tool a person would
   otherwise use. Needs ground truth and a control. Expensive enough to
   run on a schedule rather than per commit.
1. **Does it save anybody anything?** Given a real task, does a person
   or an agent finish it with less work. Needs a task, a baseline
   worker, and a way to grade the outcome. Expensive, noisy, run rarely
   and reported with its conditions attached.

A result from tier 1 says nothing about tier 2, and a result from tier 2
says nothing about tier 3. This document keeps them apart on purpose.

## What is under test

Eighteen commands. Grouped by what they claim, because what they claim
decides how they are graded.

| Group              | Commands                            | Claims                           | Tier    |
| ------------------ | ----------------------------------- | -------------------------------- | ------- |
| Retrieval          | `search`                            | The right file, ranked           | 1, 2, 3 |
| Name answers       | `refs`, `why`                       | A fact about a name, from links  | 1, 2, 3 |
| Workspace analysis | `deps`, `dupes`, `domains`          | A property of the corpus         | 1, 2    |
| Diagnosis          | `explain`, `status`, `stats`        | A true statement about the index | 1       |
| Corpus building    | `index`, `sync`, `fetch`, `compact` | The index matches the trees      | 1       |
| Interfaces         | `serve`, `mcp`, `shell`             | The same answers, over a wire    | 1, 3    |
| Setup              | `init`, `add-repo`                  | A usable workspace               | 1       |

`search` is the only group already measured at tier 2 (355 harvested
questions, ripgrep control, paired McNemar). Everything else has tier-1
unit tests and nothing above them. That gap is what this programme is
for, and it is the whole reason the tool's distinctive answers — `why`,
settings through `refs`, `deps` — are described in the documents with no
number attached.

## Preparing the environment

**The corpus is pinned and shared.** Seven workspaces, 33 repositories,
each at a recorded sha (`scripts/acceptance_corpus/corpus.json`).
Materialised into `$WSINDEX_RELEVANCE_DIR`, default
`~/.cache/wsindex-relevance`. A floating clone rots ground truth
silently, which is why nothing here clones a branch.

**Every run states its configuration.** Which model, which provider,
hybrid on or off, reranker on or off. This is not bookkeeping: two
measurements this week differed by eight questions because of a setting
nobody wrote down, and the only reason that was caught is that somebody
refused to copy a number between configurations.

**The index is rebuilt per run, not reused.** A stale index is the
cheapest way to measure last week's code.

**The control runs on the same machine, in the same pass.** `ripgrep`
for retrieval, `git log -S` and `git blame` for `why`, a manifest read
for `deps`. A control measured elsewhere is not a control.

**Failures are recorded, not retried.** A command that crashes is a
result. The field trial found three crashes and three silent coverage
failures only because nothing was re-run until it was green.

## Ground truth, per group

This is the hard part and the part that decides whether a number means
anything. Each rule below is chosen so that the answer exists
independently of this tool.

**`search`** — done. A closed issue's title is the question; the files
its fixing pull request changed are the answer. Harvested by
`scripts/harvest.py` from the indexed projects' own trackers, so neither
end was written by anybody measuring this.

**`why`** — the commit that explains a definition. Ground truth is
`git log -L <start>,<end>:<file>`, which git computes and this project
does not: the commits that touched those lines, in order. A `why` answer
is correct when the commit it names is in that list, and *useful* when
it is the one a reader would have wanted — which needs a human judgement
on a sample, recorded separately from the mechanical count.

**`refs` on a setting** — a config key and its use in code. Ground truth
is built by a deliberately generous multi-spelling search
(`snake_case`, `camelCase`, `PascalCase`, `SCREAMING_SNAKE`) over the
pinned tree, then verified by hand on a sample. The control is `rg -w`
and `rg -i` on the config spelling, which is what a person would type.

**`refs` on a symbol** — a definition and its uses. Ground truth is the
same multi-spelling search; the control is `rg -w`.

**`deps`** — a repository pair that really depends on another. Ground
truth is the manifest, which is a declaration by the repository's
authors. The interesting cases are where code and manifest disagree, and
those are graded by hand on a sample, because "undeclared" is sometimes
a fork sharing a vocabulary and sometimes a real build problem and no
rule tells them apart.

**`dupes`, `domains`** — no external ground truth exists. Graded by
sampling the output and judging it, with the sample size stated. A
number without a denominator is not reported.

**Tier 3** — a real issue, its real fix. An agent is given the issue
title and the repository at the commit before the fix, with and without
wsindex, and graded on whether it names the files the real pull request
changed and on what it spent getting there.

## What is measured

**Tier 1, per command:** exit status; whether the claim it prints is
true of the workspace; whether it warns when it should. Silence where a
warning belongs counts as a failure — three workspaces in the field
trial indexed 7% of their files and reported success.

**Tier 2, per answer:** found or not, at rank 3 and rank 10; the same
for the control; and, where the answer exists but is out of reach, at
rank 50 — the gap between those two columns is the cost of the defaults
rather than a failure of the index.

**Tier 3, per task:** solved or not, tokens spent, tool calls made,
wall clock — and the whole conversation, kept.

**An aggregate without a record is not a result you can act on.** The
first agent run reported a mean and nothing else, and two of its twelve
tasks cost more than twice as much with the tool as without. Whether a
bad answer sent the agent wandering or it merely took a long road could
not be told from a mean, so the finding could be neither fixed nor
dismissed. Transcripts are now written for every run, outside the
repository — they are a record of somebody else's code and not ours to
commit — and the per-task tool counts go into the protocol beside the
totals, because "the treatment replaced reading" and "the treatment
added to it" produce the same token figure and mean opposite things.

**A harness records what it handed over, not what it meant to hand
over.** The transcripts were added to explain two expensive tasks and
the first one explained something else: the agent had not six tools but
**212**. `--allowedTools` says what may run without asking; `--tools`
says what exists — and with only the former, every MCP server configured
on the operator's machine joined the run, this machine's mail and
calendar included. Both arms carried it, so the comparison was not
lopsided, merely not the experiment the protocol described. Two rules
follow. The harness names the tools with the flag that limits them and
passes `--strict-mcp-config` so only the server under test is loaded;
and the protocol prints the inventory each side actually reported at
startup, so a reader can see the experiment rather than trust it. The
run that found this was discarded — a measurement of a setup nobody
described cannot be repaired by reinterpreting it.

**Everywhere:** what it cost. Seconds, bytes, and tokens if any left the
machine.

## How results are interpreted

**Paired, always.** Every comparison puts the same question to two
tools or two configurations, so the test is McNemar's on the discordant
pairs, not two proportions compared by eye. `55 against 60` is not a
result; `27 only wsindex, 32 only ripgrep, p = 0.60` is.

**Reachability is counted apart from ranking.** A question whose answer
lives in a file the indexer never read is a coverage failure wearing a
retrieval failure's clothes. Fifty of 204 harvested questions are
unreachable — all Elixir, no grammar — and folding them into a hit rate
would tax every configuration equally and invisibly, and would make a
future fix to *coverage* look like a gain in *relevance*.

**A control that drowns has not answered.** `ripgrep` returning seventy
files has found the answer in the sense that matters to a script and not
in the sense that matters to a person. Counted as its own outcome.

**The gate is declared before the run.** The field trial's rule was
written down first and the trial failed it; that is the only reason the
failure was believed. A gate invented afterwards grades the answer
against a question chosen after seeing it.

**A negative result is a result and is published.** Two thirds of the
link store was measured into near-worthlessness this week and the
measurement is in the ADR.

## Protocols

Every run produces one document. Generated by the harness, not typed,
because a protocol written by hand is a protocol written after the
interesting part was forgotten.

A protocol contains, in this order:

1. **Conditions** — date, commit sha, corpus shas, full configuration,
   machine, whether the control binary was found.
1. **The gate**, quoted from before the run.
1. **What ran and what did not** — every command attempted, every
   crash, every skip and its reason.
1. **Results per tier**, with the control beside every number and the
   paired counts, not just the totals.
1. **The interpretation** — what the numbers say, what they do not say,
   and which claims in the documents they change.
1. **Raw rows** — one line per question, so anybody can recount.

Protocols live in `docs/protocols/` with the date in the filename. They
are not edited after the fact; a later run is a later protocol.

## Where it lives and what runs when

**In the repository:** the instruments (`scripts/`), the pinned corpus
and its questions (`scripts/acceptance_corpus/`), and the protocols
(`docs/protocols/`). Review artifacts and one-off probes stay out, as
they do today.

**In CI, per pull request:** tier 1 over a small workspace, plus the
existing unit gates. Fast enough to block a merge.

**In CI, weekly:** tier 2 over the routine tier, against a committed
baseline, failing when any class answers fewer questions than before.
This is the regression guard that did not exist when quality left twice
in one day.

**By hand:** tier 3, and tier 2 against a hosted model, because both
spend money and neither belongs on a schedule.

## How this document changes

The methodology is under test too, and the order is fixed: run,
**analyse the methodology**, then analyse the results. Analysing the
results of a method one does not trust is how a project convinces itself
of something.

A gap in the methodology is anything that would let a wrong answer
through unnoticed, and the evidence for one is usually a surprise — a
number that moved for no reason anybody can name. When one is found this
document is amended, the amendment is dated, and the affected runs are
repeated rather than reinterpreted.

**A defect found in one place is looked for in every other.** This is a
rule because it was broken twice. A control credited for being *concise*
rather than correct was found and fixed in `why`; found and fixed again
in the spelling question; and left standing in `refs` on symbols and on
settings, where it was worse than unfair — the truth there is a search
for four spellings and the control searches one of them, so every result
the control returned was in the truth by construction and it could not
be wrong. Two published verdicts rested on that before anybody swept.

The same shape appeared in tier 1: the coverage check counted files
against a list of suffixes wsindex claims to support, so a language it
does not support was invisible to the check written to catch exactly
that. A measurement that inherits the tool's blind spot cannot see the
tool go blind, and both of these are that.

So: when a defect is understood, name its *class* and search the other
instruments for it before reporting anything. The search is cheap and
the alternative is publishing a number twice.
