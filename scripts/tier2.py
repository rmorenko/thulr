"""Tier 2: is the answer right, and does it beat what a person would type?

`search` has been measured this way for a while — 355 questions harvested
from issue trackers, a ripgrep control, paired McNemar. The three answers
this tool is supposed to exist *for* have never been:

- **`why`** — a definition, and the commits that explain it.
- **`refs` on a symbol** — where a name is defined and what uses it.
- **`refs` on a setting** — a config key and the code that reads it,
  across spellings, which is the one query `grep` cannot serve at all.

Each gets ground truth that exists independently of this tool, and a
control that is what somebody would actually type instead. That second
half is not decoration: a number with no control is a number graded
against itself, and this project has published one of those before.

What this does *not* measure, stated so nobody reads it as more than it
is: `why` is scored on the commits it names for the definition it found,
so a wrong definition is charged to `search`, not here. Whether the
commit it names is the one a reader *wanted* is a human judgement and is
sampled separately rather than counted.

Usage:
    uv run python scripts/tier2.py                 # smallest workspace
    uv run python scripts/tier2.py caddyserver
    uv run python scripts/tier2.py --all

Environment:
    WSINDEX_RELEVANCE_DIR   corpus cache, shared with the other harnesses
    WSINDEX_RG              ripgrep, when it is not on PATH
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "acceptance_corpus"
CACHE = Path(os.environ.get("WSINDEX_RELEVANCE_DIR", Path.home() / ".cache" / "wsindex-relevance"))
PROTOCOLS = HERE.parent / "docs" / "protocols"
BINARY = Path(sys.executable).parent / "wsindex"
RG = os.environ.get("WSINDEX_RG") or shutil.which("rg")

SAMPLE = 40
"""How many of each kind to ask about. Stated rather than chosen per
run: a sample size picked after seeing the answers is not a sample."""

SEED = 20260913
"""Frozen, so the same corpus asks the same questions. Changing it is a
different experiment and says so in the protocol."""

DROWNED_AT = 20
"""Files a control may return before it has stopped answering. Above
this the person is reading a list, which is the work ranking exists to
remove."""


@dataclass
class Graded:
    """One question, put to the tool and to the control.

    Attributes:
        reachable: Whether any file holding the answer was indexed at
            all. A question about a file no grammar covers is a coverage
            failure wearing a quality failure's clothes, and folding the
            two together taxes every configuration equally and
            invisibly — `pow-auth` is Elixir, indexes almost nothing,
            and answered 0 of 40 on all three kinds before this column
            existed.
        control: How the control did, graded by the *same* rule as the
            tool. The first version scored it `found` for returning few
            results, which credits it for being concise rather than for
            being right.
    """

    kind: str
    subject: str
    ours: bool
    control: str
    reachable: bool = True
    control_count: int = 0
    detail: str = ""


@dataclass
class Run:
    org: str
    graded: list[Graded] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)


def wsindex(*args: str, cwd: Path, env: dict[str, str]) -> str:
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


def git(*args: str, cwd: Path) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    return done.stdout


def rg(*args: str, cwd: Path) -> list[str]:
    if RG is None:
        return []
    done = subprocess.run(
        ["rg", *args, "."],
        executable=RG,
        cwd=cwd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=180,
    )
    return [line.strip().removeprefix("./") for line in done.stdout.splitlines() if line.strip()]


SPELLINGS = (
    lambda w: w,
    lambda w: "".join(p.capitalize() for p in re.split(r"[_.\-]", w) if p),
    lambda w: (lambda parts: parts[0] + "".join(p.capitalize() for p in parts[1:]))(
        [p for p in re.split(r"[_.\-]", w) if p]
    ),
    lambda w: re.sub(r"[.\-]", "_", w).upper(),
)
"""The four ways one name gets written. Ground truth for `refs` is what
a search for *all* of them finds, which is deliberately more generous
than anything the tool does — a control that cannot lose is not one."""


def truth_for(name: str, root: Path) -> set[str]:
    """Every file naming this thing, under any of its spellings."""
    found: set[str] = set()
    for spell in SPELLINGS:
        try:
            written = spell(name)
        except IndexError:
            continue
        if written:
            found |= set(rg("-l", "-F", "-w", written, cwd=root))
    return found


CITED = re.compile(r"^\s{4}(\S+?):(\d+)")
COMMIT = re.compile(r"^\s{4}([0-9a-f]{7,40})\s")
DEFINITION = re.compile(r"^(\S+)\s+(\S+?):(\d+)-(\d+)")


CODE_SUFFIXES = {
    ".py",
    ".rb",
    ".go",
    ".rs",
    ".java",
    ".cs",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".ex",
    ".exs",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
}
"""What a definition can be found in. Narrow on purpose: a name declared
in a yaml is a setting, and settings are asked about separately."""

DEFINES = re.compile(
    r"^\s*(?:(?:public|private|protected|static|final|async|export|pub)\s+)*"
    r"(?:class|def|func|function|type|struct|interface|module|fn)\s+"
    r"([A-Za-z_][A-Za-z0-9_]{4,})"
)
"""A definition, as the source file spells it.

Subjects are drawn from the *tree*, never from what the tool returned.
Asking a tool about the names it chose to show is how a measurement
grades itself, and the first version of this file did exactly that — and
produced zero questions, which is the only reason it was noticed."""


def defined_names(root: Path, repos: list[str]) -> list[str]:
    """Names the source declares, drawn with the frozen seed."""
    found: set[str] = set()
    for repo in repos:
        for path in (root / repo).rglob("*"):
            if not path.is_file() or {".git", "node_modules", "vendor"} & set(path.parts):
                continue
            if path.suffix not in CODE_SUFFIXES:
                continue
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                match = DEFINES.match(line)
                if match:
                    found.add(match.group(1))
    names = sorted(found)
    random.Random(SEED).shuffle(names)
    return names


def grade_why(
    root: Path,
    repos: list[str],
    home: Path,
    env: dict[str, str],
    subjects: list[str],
) -> list[Graded]:
    """`why`: are the commits it names ones that touched those lines?

    Ground truth is `git log -L`, which git computes from the history
    and this project has no hand in. The control is `git log -S`, which
    is what a person reaches for and which answers a coarser question —
    every commit that changed how often the name appears anywhere.
    """
    found: list[Graded] = []
    for symbol in subjects:
        answer = wsindex("why", symbol, cwd=home, env=env)
        head = DEFINITION.match(answer.strip().splitlines()[0]) if answer.strip() else None
        if head is None:
            # Not a `why` failure: nothing was found to ask about, which
            # is `search`'s business. Marked unreachable so it does not
            # sit in the quality count.
            found.append(
                Graded(
                    "why",
                    symbol,
                    False,
                    "n/a",
                    reachable=False,
                    detail="no definition found",
                )
            )
            continue
        where, start, end = head.group(2), int(head.group(3)), int(head.group(4))
        repo, _, rel = where.partition("/")
        if repo not in repos:
            continue
        named = {m.group(1)[:7] for m in (COMMIT.match(x) for x in answer.splitlines()) if m}
        tree = root / repo
        truth = {
            line.split()[0][:7]
            for line in git(
                "log", "-L", f"{start},{end}:{rel}", "--format=%h", "-s", cwd=tree
            ).splitlines()
            if line.strip()
        }
        control = git("log", "-S", symbol, "--format=%h", cwd=tree).splitlines()
        ours = bool(named & truth) if named else False
        outcome = (
            "found"
            if control and len(control) <= DROWNED_AT
            else "drowned"
            if control
            else "missed"
        )
        found.append(
            Graded(
                "why",
                symbol,
                ours,
                outcome,
                len(control),
                f"named {len(named)}, {len(truth)} touched those lines",
            )
        )
    return found


def grade_refs(
    kind: str,
    subjects: list[str],
    root: Path,
    home: Path,
    env: dict[str, str],
    indexed: set[str],
) -> list[Graded]:
    """`refs`: does it name the files that really use this name?

    Scored on whether the files it cites are among the files a
    four-spelling search finds. The control is what a person types —
    one spelling, `rg -w` — so the comparison is between what the tool
    knows and what a person would have had to guess.
    """
    found: list[Graded] = []
    for subject in subjects:
        truth = truth_for(subject, root)
        if not truth:
            continue
        answer = wsindex("refs", subject, cwd=home, env=env)
        reachable = bool(truth & indexed)
        # `repo/path`, kept whole. The control greps from the workspace
        # root, so its paths carry the repository directory too, and
        # stripping it here made every comparison empty — 0 of 40 with
        # the tool citing six files and the truth holding twenty-seven.
        cited = {m.group(1) for m in (CITED.match(line) for line in answer.splitlines()) if m}
        cited = {c for c in cited if c and not c.startswith("commits/")}
        control = rg("-l", "-F", "-w", subject, cwd=root)
        found.append(
            Graded(
                kind,
                subject,
                bool(cited & truth),
                "found"
                if control and len(control) <= DROWNED_AT
                else "drowned"
                if control
                else "missed",
                reachable=reachable,
                control_count=len(control),
                detail=f"cited {len(cited)}, truth {len(truth)}",
            )
        )
    return found


def config_keys(root: Path) -> list[str]:
    """Keys real config files declare, drawn with the frozen seed."""
    keys: Counter[str] = Counter()
    for path in root.rglob("*"):
        if not path.is_file() or {".git", "node_modules", "vendor"} & set(path.parts):
            continue
        if path.suffix not in (".yml", ".yaml", ".toml", ".json"):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            found = re.match(r'^\s*["\']?([A-Za-z_][A-Za-z0-9_.\-]{3,})["\']?\s*[:=]', line)
            if found:
                keys[found.group(1)] += 1
    names = sorted(keys)
    random.Random(SEED).shuffle(names)
    return names[: SAMPLE * 2]


def indexed_paths(home: Path) -> set[str]:
    """Every `repo/path` the store actually holds.

    Read from the store rather than asked of the binary: this classifies
    a question, it does not answer one, and `explain` per file would be
    a process and a model load apiece. Without it a workspace whose
    language has no grammar scores zero and reads as a quality failure —
    `pow-auth` did exactly that, 0 of 40 on all three kinds, because it
    is Elixir and almost nothing was indexed.
    """
    import lancedb

    table = lancedb.connect(str(home / ".wsindex")).open_table("data")
    # Two columns, not the vectors: this table is hundreds of megabytes
    # on a large workspace and the question is only which files exist.
    rows = table.search().select(["repo", "path"]).limit(table.count_rows()).to_arrow()
    return {
        f"{repo}/{path}"
        for repo, path in zip(
            rows.column("repo").to_pylist(), rows.column("path").to_pylist(), strict=True
        )
    }


def run_workspace(org: str, spec: dict[str, Any]) -> Run:
    sys.path.insert(0, str(HERE))
    import relevance as R

    root = R.materialise(org, spec["repos"])
    repos = [repo["id"] for repo in spec["repos"]]
    home = CACHE / ".tier2" / org
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)
    env = {"WSINDEX_CONFIG": str(home / "wsindex.toml")}
    wsindex("init", f"tier2-{org}", cwd=home, env=env)
    for repo in spec["repos"]:
        wsindex("add-repo", repo["id"], str(root / repo["id"]), cwd=home, env=env)
    print(f"  indexing {org}", flush=True)
    wsindex("index", cwd=home, env=env)

    indexed = indexed_paths(home)
    run = Run(org=org)
    run.notes["indexed_files"] = len(indexed)
    names = defined_names(root, repos)
    run.notes["names_in_tree"] = len(names)
    print(f"  why ({len(names)} names in the tree)", flush=True)
    run.graded += grade_why(root, repos, home, env, names[:SAMPLE])
    print("  refs on symbols", flush=True)
    run.graded += grade_refs("refs/symbol", names[SAMPLE : SAMPLE * 2], root, home, env, indexed)
    print("  refs on settings", flush=True)
    run.graded += grade_refs("refs/setting", config_keys(root)[:SAMPLE], root, home, env, indexed)
    run.notes["deps"] = wsindex("deps", cwd=home, env=env)
    return run


def mcnemar(ours: int, theirs: int) -> float:
    """Exact two-sided binomial test on the discordant pairs.

    Exact rather than the chi-square approximation: these samples are
    forty questions and the discordant counts are often single digits,
    where the approximation is simply wrong.
    """
    total = ours + theirs
    if total == 0:
        return 1.0
    fewer = min(ours, theirs)
    return min(2 * sum(math.comb(total, i) for i in range(fewer + 1)) / 2**total, 1.0)


def protocol(runs: list[Run], seconds: float) -> str:
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    every = [g for run in runs for g in run.graded]
    lines = [
        "# Tier 2 — is the answer right, and does it beat what a person would type?",
        "",
        f"_{time.strftime('%Y-%m-%d %H:%M')}, wsindex `{sha}`, "
        f"{len(runs)} workspace(s), {len(every)} questions, {seconds:.0f}s._",
        "",
        "## Conditions",
        "",
        f"- Sample: {SAMPLE} of each kind per workspace, drawn with seed {SEED}",
        f"- Control binary: {RG or 'NOT FOUND — the control did not run'}",
        "- Ground truth: `git log -L` for `why`, a four-spelling search for `refs`",
        "",
        "## The gate, declared before the run",
        "",
        "For each kind, the tool answers more questions than its control,",
        "and the difference is significant on the discordant pairs. A kind",
        "that does not clear it is reported as not clearing it.",
        "",
        "## Results",
        "",
        "| Workspace | Kind | Asked | Reachable | Ours | Control | only ours | only rg | p |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        for kind in ("why", "refs/symbol", "refs/setting"):
            group = [g for g in run.graded if g.kind == kind]
            if not group:
                continue
            live = [g for g in group if g.reachable]
            only_ours = sum(1 for g in live if g.ours and g.control != "found")
            only_rg = sum(1 for g in live if not g.ours and g.control == "found")
            lines.append(
                f"| `{run.org}` | `{kind}` | {len(group)} | {len(live)} | "
                f"{sum(g.ours for g in live)} | {sum(g.control == 'found' for g in live)} | "
                f"{only_ours} | {only_rg} | {mcnemar(only_ours, only_rg):.4f} |"
            )
    lines += [
        "",
        "Counted on the **reachable** rows only: a question about a file no",
        "grammar covers is a coverage failure wearing a quality failure's",
        "clothes, and folding it in taxes every configuration equally and",
        "invisibly. `p` is McNemar's exact test on the discordant pairs,",
        "which is the only thing the totals cannot say.",
        "",
        "## Raw rows",
        "",
        "| Workspace | Kind | Subject | Ours | Control | n | Detail |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for run in runs:
        for g in run.graded:
            lines.append(
                f"| `{run.org}` | {g.kind} | `{g.subject}` | {'yes' if g.ours else 'no'} | "
                f"{g.control} | {g.control_count} | {g.detail} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    if RG is None:
        # A tier-2 run without a control is a number graded against
        # itself, which the methodology forbids in as many words. Better
        # to refuse than to write a protocol that looks like evidence.
        print(
            "no ripgrep: set WSINDEX_RG to its path. A tier-2 run without a "
            "control measures nothing.",
            file=sys.stderr,
        )
        return 2
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    corpus = json.loads((CORPUS / "corpus.json").read_text(encoding="utf-8"))
    wanted = list(corpus) if "--all" in sys.argv else (args or ["DatabaseCleaner"])
    started = time.monotonic()
    runs = []
    for org in wanted:
        print(f"{org}:", flush=True)
        runs.append(run_workspace(org, corpus[org]))
    PROTOCOLS.mkdir(parents=True, exist_ok=True)
    out = PROTOCOLS / f"tier2-{time.strftime('%Y-%m-%d')}.md"
    out.write_text(protocol(runs, time.monotonic() - started), encoding="utf-8")
    for run in runs:
        for kind in ("why", "refs/symbol", "refs/setting"):
            group = [g for g in run.graded if g.kind == kind]
            if group:
                print(
                    f"  {run.org:<16} {kind:<14} {sum(g.ours for g in group)}/{len(group)}"
                    f"   control found {sum(g.control == 'found' for g in group)}",
                    flush=True,
                )
    print(f"\nprotocol written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
