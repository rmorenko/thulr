# wsindex, for whoever decides whether a team adopts it

## What it is, in one paragraph

A command-line tool that indexes the several git repositories a team
works in and answers questions about them with exact file and line
numbers. It is one binary, no account, no per-seat cost, and by default
it runs entirely on the developer's own machine.

**That default is a posture with a price, and the price is measured.**
On 154 questions taken from the issue trackers of the projects being
indexed, the fully local default finds the right file in the top ten 65
times and `ripgrep` finds it 60 — a tie, inside noise. A hosted reranker, which sends a query
and about forty candidate chunks per search and never the repository,
takes it to 85. A hosted embedder as well, which does send every chunk
once, takes it to 109. Four postures, three of them defensible, and the
choice is yours rather than this document's.

If the answer has to be "nothing leaves", the default is already the row
to standardise on: fusing a lexical pass with the vector one is what took
it to 65 from the 55 it managed before, and it sends nothing either way.
If you have hardware and a
closed network, the same argument points at running a larger model on
your own infrastructure — which this supports and which has **not** been
measured here, so treat it as a direction rather than a number.

Everything below is measured on twenty real codebases that are not its
own — 105 repositories from twenty GitHub organizations, chosen to
include the cases where it would struggle. The measurements, and how they
were taken, are in [field-trial.md](field-trial.md).

## What a team gets

**Search that keeps working as the codebase grows.** On the largest
codebase tested — DBeaver, 11 786 files — wsindex put the right file in
the top three for every identifier question asked. `ripgrep`, the tool
people actually use today, found one in four and returned over twenty
files for two more. The value is not that it beats grep on a small repo;
it is that it keeps working when grep stops being usable.

**One question across every repository at once.** Teams that split code,
docs, infrastructure and SDKs across repositories currently rely on
somebody knowing which repo holds what. This removes that dependency, and
it is the reason the tool exists.

**A duplication report that groups by cause.** `wsindex dupes` finds the
same code in two places and collapses the result by the directories
involved, so two copies of a vendored library read as one fact rather
than three hundred findings. It found real duplication in 47 of the
repositories tested.

**Onboarding evidence.** `wsindex domains` reads what a repository is
made of and which files keep changing together across package
boundaries — the pairs where two modules are coupled but not about the
same subject are the ones worth a conversation.

**Nothing leaves the machine.** This is a design principle, not a
setting: no telemetry, no cloud call, no code sent to a model provider.
For a team that cannot send source to a third party, this is the whole
reason to look at it.

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

**It does not yet answer questions asked in plain English.** The trial
put 102 questions phrased the way a person thinks, deliberately avoiding
the words used in the code. wsindex placed the right answer in its top
three for one of them.

This is worth reading carefully in both directions. `ripgrep` found
**none** of them, so the gap is real and your developers are living with
it today, and anyone selling you "ask your codebase a question" as a
finished feature of *this* tool would be describing the default wrongly.

But the ceiling is the model, and that is now measured rather than
assumed: the same pipeline with a frontier code embedder and reranker
answers 12 of 23 in the top three. The default is a small local model
chosen so that nothing leaves the machine. If your team does not need
that guarantee, the gap is a configuration away rather than a rewrite —
and if it does, the guarantee is why you are reading this page.

**It is not finished software, though it is less unfinished than the
trial found it.** Three of the twenty workspaces could not be indexed at
all — two crashed on a repository with more than ~17 900 files, one on a
twenty-year-old commit message containing a non-UTF-8 character — and
three more indexed almost nothing while reporting success. All of that
is fixed and tested. What is not fixed is the class of question below.

**It does not support every language.** Sixteen languages get a real
syntax tree. Elixir, Scala, Swift and Objective-C get nothing at all
unless somebody adds a configuration entry per repository.

## Where it fits, and where it does not

**A good fit:** several repositories, at least one of them large, a
polyglot mix drawn from the supported languages, and a hard requirement
that source code stays on the machine. The bigger and more scattered the
codebase, the more it is worth.

**A poor fit today:** a single small repository — grep is enough; a
workspace in an unsupported language — it will index your READMEs and
nothing else; a team that wants natural-language questions answered out
of the box — that part needs a model the default is not.

## How to decide

Pick your largest repository and your most scattered workspace. Install
it, index, and give two developers a week with `-k 50 --kind code` as
their habit. Ask them one question afterwards: *when you needed to find
where something lived, did you reach for this or for grep?*

That is a cheaper experiment than any argument about it, and it is the
one this trial could not run — the twenty codebases were strangers'. On
your own code, with your own people, the answer may differ, and it is the
only answer that decides anything.
