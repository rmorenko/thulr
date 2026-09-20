"""Tier 3: does it save anybody anything?

The question this project has been unable to answer since the beginning.
Every number above this measures a *rank*, and a rank is not a task
finished with less work.

**The agent here is a fixed policy, not a language model, and that is the
design rather than a shortcut.** An LLM agent measures the model at least
as much as the tool: run it twice and it reads different files. What
both tools actually do for a worker is change *what they put in front of
them*, so that is what is measured — how much a reader must consume
before the answer is under their eyes.

Two workers, the same questions, the same stopping rule:

- **grep** takes the query's own words by the frozen rule `relevance.py`
  uses, runs `rg -n` on each in turn, and reads a window around every
  match — `WINDOW` lines either side, which is what `rg -C` shows and
  what a person actually reads. Its *best* shot, not its worst: charging
  it for whole files is charging it for a tool nobody uses.
- **thulr** runs one search and reads the chunks it ranked, in order —
  the real line range of each, taken off disk, not the one-line snippet
  the terminal printed. Charging it for the preview was the first
  version of this file and it flattered the result by two orders of
  magnitude.

Both stop the moment a file holding the answer is in front of them. The
cost is what they read to get there.

What this does not measure, said plainly: a real worker skims, gives up
on a file after two lines, and rewrites the query when the first attempt
fails. This models none of that. It measures the size of the pile each
tool hands over, which is the part the tool controls and the only part
that is the same for every reader.

Tokens are counted as characters over four — the same rule on both
sides, so the comparison holds even though the constant is a convention.

Usage:
    uv run python scripts/tier3.py                 # routine tier
    uv run python scripts/tier3.py caddyserver
    uv run python scripts/tier3.py --full

Environment:
    THULR_RELEVANCE_DIR   corpus cache, shared with the other harnesses
    THULR_RG              ripgrep, when it is not on PATH
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import relevance as R  # noqa: E402  - the corpus, the control and the term rule

CORPUS = HERE / "acceptance_corpus"
CACHE = R.CACHE
PROTOCOLS = HERE.parent / "docs" / "protocols"
BINARY = Path(sys.executable).parent / "thulr"

BUDGET = 120_000
"""Tokens a worker may read before it has failed.

Generous on purpose — it is about a large context window — because the
interesting number is what was spent to succeed, and a cap that bites
often would quietly turn a cost measurement into a recall one."""

DEPTH = 150
"""How many ranked hits the thulr worker may walk.

Deep enough that `BUDGET` is what stops it, which is the only way the
two workers are under the same rule. At twenty — the first version —
thulr stopped at 8 621 tokens while grep was still going at 118 310,
and the found-rates that produced said more about the two cut-offs than
about either tool. A chunk is around 800 tokens, so a hundred and fifty
of them is the budget."""

WINDOW = 20
"""Lines either side of a match the grep worker reads.

`rg -C 20` is a generous reading of what somebody does with a hit, and
generous is the point: a control given its worst tool is not a control.
The first version of this charged it for whole files and reported
thulr cheaper on 44 of 44 — true of that comparison and of no other."""

TERMS = 4
"""How many of the query's words the grep worker will try. It tries them
in the frozen order `relevance.py` derives — most specific first — and
reads what each returns before moving on, which is what somebody does."""


def tokens(text: str) -> int:
    """Characters over four. A convention, applied identically to both."""
    return max(1, len(text) // 4)


@dataclass
class Attempt:
    """What one worker spent on one question."""

    found: bool
    cost: int
    read: int = 0
    note: str = ""


@dataclass
class Task:
    """One task, put to both workers.

    Attributes:
        reachable: Whether any file holding the answer was indexed at
            all. A task about a file no grammar covers is a coverage
            failure, not a cost one, and tier 2 counts those apart while
            this used to fold them in — `pow-auth` is Elixir, indexes 30
            of 423 files, and reported 0 against grep's 35, which had to
            be subtracted by hand every time the result was quoted.
    """

    question: str
    answers: tuple[str, ...]
    ours: Attempt
    theirs: Attempt
    reachable: bool = True


@dataclass
class Run:
    org: str
    tasks: list[Task] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)


def thulr(*args: str, cwd: Path, env: dict[str, str]) -> str:
    done = subprocess.run(
        [str(BINARY), *args],
        cwd=cwd,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=900,
    )
    return done.stdout


def windows(root: Path, rel: str, hits: list[int]) -> int:
    """Tokens in the merged `WINDOW`-line windows around some matches."""
    try:
        lines = (root / rel).read_text(errors="replace").splitlines()
    except OSError:
        return 0
    wanted: set[int] = set()
    for line in hits:
        wanted |= set(range(max(0, line - 1 - WINDOW), min(len(lines), line + WINDOW)))
    return tokens("\n".join(lines[n] for n in sorted(wanted))) if wanted else 0


def grep_worker(question: str, answers: set[str], root: Path) -> Attempt:
    """Terms, then a window around each match, until the answer shows up.

    Windows rather than whole files: `rg -C 20` is what a person looks
    at, and a control charged for opening every file whole is a control
    handed its worst tool. This is the generous reading on purpose.
    """
    spent = 0
    opened = 0
    seen: set[str] = set()
    for term in R.terms(question)[:TERMS]:
        found = R.control_matches(root, term)
        if found is None:
            break
        for rel, at in found.items():
            if rel in seen:
                continue
            seen.add(rel)
            spent += windows(root, rel, at)
            opened += 1
            if rel in answers:
                return Attempt(True, spent, opened, f"after {opened} files, term `{term}`")
            if spent > BUDGET:
                return Attempt(False, spent, opened, f"budget after {opened} files")
    return Attempt(False, spent, opened, f"exhausted {len(seen)} files")


def chunk_tokens(root: Path, where: str, span: str) -> int:
    """Tokens in the lines a hit actually covers, read off disk.

    Not the snippet the terminal printed. That is one line, and charging
    for it reported a median of 32 tokens against grep's 13 237 — a
    number about output formatting, not about what a reader consumes.
    """
    first, _, last = span.partition("-")
    try:
        lines = (root / where).read_text(errors="replace").splitlines()
        start, end = int(first), int(last or first)
    except (OSError, ValueError):
        return 0
    return tokens("\n".join(lines[max(0, start - 1) : end])) or 1


def thulr_worker(
    question: str, answers: set[str], home: Path, env: dict[str, str], root: Path
) -> Attempt:
    """One search, then its chunks in rank order.

    Charged for the chunk's real line range, because a chunk with a line
    range is what this hands over instead of a path — and that difference
    is the whole hypothesis under test.
    """
    out = thulr("search", question, "-k", str(DEPTH), cwd=home, env=env)
    spent = 0
    opened = 0
    for line in out.splitlines():
        parts = line.split("  ", 2)
        if len(parts) < 3 or ":" not in parts[0]:
            continue
        where, _, span = parts[0].rpartition(":")
        spent += chunk_tokens(root, where, span)
        opened += 1
        if where in answers:
            return Attempt(True, spent, opened, f"at rank {opened}")
        if spent > BUDGET:
            return Attempt(False, spent, opened, f"budget after {opened} chunks")
    return Attempt(False, spent, opened, f"not in {opened} hits")


def mcnemar(ours: int, theirs: int) -> float:
    total = ours + theirs
    if total == 0:
        return 1.0
    fewer = min(ours, theirs)
    return min(2 * sum(math.comb(total, i) for i in range(fewer + 1)) / 2**total, 1.0)


def indexed_paths(home: Path) -> set[str]:
    """Every `repo/path` the store holds, for the reachability column.

    Read from the store rather than asked of the binary: this classifies
    a task, it does not answer one.
    """
    import lancedb

    table = lancedb.connect(str(home / ".thulr")).open_table("data")
    rows = table.search().select(["repo", "path"]).limit(table.count_rows()).to_arrow()
    return {
        f"{repo}/{path}"
        for repo, path in zip(
            rows.column("repo").to_pylist(), rows.column("path").to_pylist(), strict=True
        )
    }


def run_workspace(org: str, spec: dict[str, Any]) -> Run:
    root = R.materialise(org, spec["repos"])
    home = CACHE / ".tier3" / org
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)
    env = {"THULR_CONFIG": str(home / "thulr.toml")}
    thulr("init", f"tier3-{org}", cwd=home, env=env)
    for repo in spec["repos"]:
        thulr("add-repo", repo["id"], str(root / repo["id"]), cwd=home, env=env)
    print(f"  indexing {org}", flush=True)
    thulr("index", cwd=home, env=env)
    run = Run(org=org)

    harvested = json.loads((CORPUS / "harvested" / f"{org}.json").read_text(encoding="utf-8"))[
        "questions"
    ]
    indexed = indexed_paths(home)
    run.notes["indexed_files"] = len(indexed)
    for item in harvested:
        answers = {item["truth"], *item.get("also_valid", [])}
        question = item["text"]
        run.tasks.append(
            Task(
                question=question,
                answers=tuple(sorted(answers)),
                ours=thulr_worker(question, answers, home, env, root),
                theirs=grep_worker(question, answers, root),
                reachable=bool(answers & indexed),
            )
        )
    return run


def protocol(runs: list[Run], seconds: float) -> str:
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    every = [t for run in runs for t in run.tasks if t.reachable]
    both = [t for t in every if t.ours.found and t.theirs.found]
    lines = [
        "# Tier 3 — does it save anybody anything?",
        "",
        f"_{time.strftime('%Y-%m-%d %H:%M')}, thulr `{sha}`, "
        f"{len(runs)} workspace(s), {len(every)} tasks, {seconds:.0f}s._",
        "",
        "## Conditions",
        "",
        "- Tasks: the harvested questions — a closed issue's title, and the",
        "  files the pull request that closed it changed.",
        "- Workers: a fixed reading policy, not a language model. `grep`",
        "  reads whole files in the order `rg -l` names them; `thulr`",
        "  reads ranked chunks. Both stop when an answer file is in front",
        "  of them.",
        f"- Budget: {BUDGET} tokens, counted as characters over four, the",
        "  same rule on both sides.",
        "",
        "## The gate, declared before the run",
        "",
        "On the tasks both workers finish, thulr puts fewer tokens in",
        "front of the reader, and finishes at least as many tasks overall.",
        "",
        "## Results",
        "",
        "| Workspace | Tasks | Reachable | ws found | grep found | only ws | only grep | p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        live = [t for t in run.tasks if t.reachable]
        only_ours = sum(1 for t in live if t.ours.found and not t.theirs.found)
        only_rg = sum(1 for t in live if not t.ours.found and t.theirs.found)
        lines.append(
            f"| `{run.org}` | {len(run.tasks)} | {len(live)} | "
            f"{sum(t.ours.found for t in live)} | "
            f"{sum(t.theirs.found for t in live)} | {only_ours} | {only_rg} | "
            f"{mcnemar(only_ours, only_rg):.4f} |"
        )
    if both:
        ours = sorted(t.ours.cost for t in both)
        theirs = sorted(t.theirs.cost for t in both)
        middle = len(both) // 2
        cheaper = sum(1 for t in both if t.ours.cost < t.theirs.cost)
        lines += [
            "",
            f"## What it cost, on the {len(both)} tasks both finished",
            "",
            "| Worker | Median tokens | Mean | Worst |",
            "| --- | ---: | ---: | ---: |",
            f"| thulr | {ours[middle]} | {sum(ours) // len(ours)} | {ours[-1]} |",
            f"| grep | {theirs[middle]} | {sum(theirs) // len(theirs)} | {theirs[-1]} |",
            "",
            f"thulr was cheaper on **{cheaper} of {len(both)}**.",
        ]
    lines += [
        "",
        "## Raw rows",
        "",
        "| Workspace | ws | cost | grep | cost | question |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    for run in runs:
        for t in run.tasks:
            lines.append(
                f"| `{run.org}` | {'found' if t.ours.found else 'no'} | {t.ours.cost} | "
                f"{'found' if t.theirs.found else 'no'} | {t.theirs.cost} | "
                f"{t.question[:70]} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    if R.RG is None:
        print("no ripgrep: set THULR_RG. Tier 3 has no control without it.", file=sys.stderr)
        return 2
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    corpus = json.loads((CORPUS / "corpus.json").read_text(encoding="utf-8"))
    wanted = (
        list(corpus)
        if "--full" in sys.argv
        else (args or [o for o, c in corpus.items() if c["tier"] == "routine"])
    )
    started = time.monotonic()
    runs = []
    for org in wanted:
        if not (CORPUS / "harvested" / f"{org}.json").is_file():
            continue
        print(f"{org}:", flush=True)
        runs.append(run_workspace(org, corpus[org]))
        last = runs[-1]
        print(
            f"  {len(last.tasks)} tasks; ws {sum(t.ours.found for t in last.tasks)}, "
            f"grep {sum(t.theirs.found for t in last.tasks)}",
            flush=True,
        )
    PROTOCOLS.mkdir(parents=True, exist_ok=True)
    out = PROTOCOLS / f"tier3-{time.strftime('%Y-%m-%d')}.md"
    out.write_text(protocol(runs, time.monotonic() - started), encoding="utf-8")
    print(f"\nprotocol written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
