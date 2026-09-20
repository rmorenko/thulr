# wsindex, for whoever decides whether a team adopts it

## What it is, in one paragraph

A command-line tool that indexes the several git repositories a team
works in and answers questions about them with exact file and line
numbers. It is one binary, no account, no per-seat cost, and by default
it runs entirely on the developer's own machine.

## The decision, stated before the evidence

**There is a class of question about unfamiliar code that `grep` answers
zero of, and it is roughly half of what a developer joining a codebase
asks.** 42 such questions were written by a tester before wsindex was
allowed to run, with every word of four letters or more mechanically
checked absent from the answer file. `ripgrep` found none. wsindex finds
21 of them — **with a hosted embedder**. With the model that ships, 1.

So the two things a team wants from this tool pull against each other,
and you should meet that here rather than at a security review:

- *"Nothing leaves our machines"* — available, and already ahead of the
  control on the questions grep can also answer.
- *"Ask the codebase a question in words"* — available, and at its best
  it sends every chunk to a hosted embedder once.

Between them sits a third choice that did not exist when this page was
first written: `[rewrite]` keeps the index on your machines and sends
only the question, and it is worth more per byte than either. It does not
close the gap — it narrows it. Choosing among the three is the adoption
decision; everything below is what each buys.

## What a team gets

**Half the joining developer's questions, without spending a senior's
attention.** That is not a metaphor for the 42 questions above — it is
literally how they were written. Today the cost of those questions is
weeks of someone's time, paid in interruptions.

**Change safety across repositories.** A setting written `max_retries`
in one service's yaml is read as `MaxRetries` in another's Go, and no
`grep` flag crosses that gap — measured, 64 of 76 against a control of
**zero**. `refs` reports `unresolved` when a key is read somewhere and
declared nowhere, which is a drift signal rather than a search result.
The failure it prevents is silent: a rename that looks complete and is
not.

**Architectural memory that outlives the authors.** `why` walks a
definition back to the commits that wrote it and their messages — where
the reasoning behind a design actually survives. It named a commit that
really touched those lines 199 times of 202, against `git log -S` at 174.

Neither of those two uses a model at all. They are exact walks over a
link graph, identical on every configuration, and no vendor can improve
or withdraw them.

**One question across every repository at once.** Teams that split code,
docs, infrastructure and SDKs across repositories rely on somebody
knowing which repo holds what. On 14 questions whose answer sits in a
different repository from the one you would open first, wsindex found 12
and `ripgrep` 6.

**Search that keeps working as the codebase grows.** On the largest
codebase tested — DBeaver, 11 786 files — wsindex put the right file in
the top three for every identifier question asked. `ripgrep` found one in
four and returned over twenty files for two more. The value is not that
it beats grep on a small repo; it is that it keeps working when grep
stops being usable.

**A duplication report that groups by cause.** `wsindex dupes` finds the
same code in two places and collapses the result by the directories
involved, so two copies of a vendored library read as one fact rather
than three hundred findings. It found real duplication in 47 of the
repositories tested.

**Onboarding evidence.** `wsindex domains` reads what a repository is
made of and which files keep changing together across package
boundaries — the pairs where two modules are coupled but not about the
same subject are the ones worth a conversation.

## The posture is a choice you can defend

Four configurations, and a security officer can be given an exact answer
about each rather than a reassurance:

| Configuration                 | What leaves the machine  | Finds it (of 204) |
| ----------------------------- | ------------------------ | ----------------: |
| the default                   | nothing                  |                98 |
| hosted reranker               | the query and ~40 chunks |               109 |
| hosted embedder as well       | every chunk, once        |               132 |
| `ripgrep`, what you use today | —                        |                71 |

The middle row is the one most teams miss: the index stays where it is
and only the query and about forty candidate chunks per search go
anywhere — never the repository.

**And one option is cheaper than any of them.** `[rewrite]` sends the
question a developer typed and no code at all. It is quoted apart from
the table rather than rescaled into it, because it was measured on a
different corpus: on 355 harvested questions it takes the fully local
configuration from 138 answers to 158 (p = 0.0055) and the hosted one
from 192 to 217 (p = 0.0002). The largest measured gain per byte sent, by
a wide margin, and the only one that can be pointed at a model inside
your own network and keep the whole promise.

Two things a security review will ask, and should hear first. The
question itself can be sensitive — *"why does the Acme Bank
reconciliation job drop rows"* names a client — so this is less than the
rows above and not nothing. And a small model will not do: three billion
parameters measured worse than leaving the stage off and seven was
break-even, because the gain is the model knowing what code is usually
called.

See [for-security.md](for-security.md) for what opens a socket and when.

If you have hardware and a closed network, the same argument points at
running a larger model on your own infrastructure. That is supported and
has **not** been measured here, so treat it as a direction rather than a
number.

## What it costs

|                                          | Measured                              |
| ---------------------------------------- | ------------------------------------- |
| First index, mid-size repo (2 000 files) | 37 seconds                            |
| First index, large repo (11 800 files)   | 4 minutes 18 seconds                  |
| Re-index after no changes                | under a second, whatever the size     |
| Disk, large workspace                    | 349 MB for 125 000 chunks             |
| Ongoing cost                             | none — no server, no licence, no seat |

Setup is three commands per workspace and it is a developer's own
decision; there is nothing central to provision.

## What it does not do

**It does not help a coding agent.** Nine measurements, including three
that asked only where code lives and one that removed the shell from the
agent entirely. If somebody proposes this as an AI-productivity purchase,
the numbers are in [for-agents.md](for-agents.md) and they say no.

**It does not beat grep when the developer knows the identifier.** In the
top *three* the local default manages 62 against ripgrep's 71, which is
noise either way. This changes nothing about that, and a team that hears
otherwise from us should distrust the rest.

**Plain English does not work on the default model.** 1 of 42, against 21
with a hosted embedder and reranker. The limit is the model, measured
four ways: no available local model beats the one that ships, and the two
trained on code did worse. `[rewrite]` narrows the gap without sending
code, at the price of a model call per search, but does not close it. This is a configuration away, not a rewrite —
but it is not what `wsindex init` gives you.

**It is not finished software, though it is less unfinished than the
field trial found it.** Three of the twenty trial workspaces could not be
indexed at all — two crashed on a repository with more than ~17 900
files, one on a twenty-year-old commit message containing a non-UTF-8
character — and three more indexed almost nothing while reporting
success. All of that is fixed and tested.

**It does not support every language, though the list has grown.**
Thirty-three languages and formats are claimed, including the three that
used to be the reason to walk away — Scala, Swift and Objective-C — plus
Elixir, SQL, HCL/Terraform, shell and the config formats. Anything not
claimed is skipped rather than indexed as text, and `wsindex explain`
on any source file says which it is.

## Where it fits, and where it does not

**A good fit:** several repositories, at least one of them large, people
who regularly arrive in code they did not write, and a decision already
made about whether source may be sent to a model provider.

**A poor fit today:** a single small repository — grep is enough; a team
that wants natural-language questions answered *and* nothing leaving the
machine — those are not the same configuration; a team looking for agent
productivity — measured, and it is not there.

## How to decide

Pick your largest repository and your most scattered workspace. Install
it, index, and give two developers a week. Ask them one question
afterwards: *when you needed to find where something lived, did you reach
for this or for grep?*

That is a cheaper experiment than any argument about it, and it is the
one the field trial could not run — the twenty codebases were strangers'.
On your own code, with your own people, the answer may differ, and it is
the only answer that decides anything.

Everything above is measured on twenty real codebases that are not its
own — 105 repositories from twenty GitHub organizations, chosen to
include the cases where it would struggle. The measurements, and how they
were taken, are in [field-trial.md](field-trial.md).
