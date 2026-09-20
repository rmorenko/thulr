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
    THULR_RELEVANCE_DIR   corpus cache, shared with the other harnesses
    THULR_RG              ripgrep, when it is not on PATH
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
CACHE = Path(os.environ.get("THULR_RELEVANCE_DIR", Path.home() / ".cache" / "thulr-relevance"))
PROTOCOLS = HERE.parent / "docs" / "protocols"
BINARY = Path(sys.executable).parent / "thulr"
RG = os.environ.get("THULR_RG") or shutil.which("rg")

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


def spelled_apart(name: str, root: Path) -> tuple[set[str], set[str]]:
    """Files naming this thing *as written*, and files naming it otherwise.

    The second set is the whole claim the documents make about settings:
    a key is `max_retries` in the yaml and `MaxRetries` in the code that
    reads it, and neither `rg -w` nor `rg -i` bridges those. Scoring a
    hit on the union let both sides win by pointing at the config file
    the key is declared in — measured, that is most of why the control
    scored 165 of 214 on a question it was supposed to be unable to
    answer.

    Returns:
        Files using the spelling given, and files using another one and
        not that one.
    """
    # Everything a person can reach from the spelling in front of them:
    # the word itself, and the word ignoring case — which already
    # catches `MAX_RETRIES`. Counting that as "another spelling" made
    # the control score 24 of 25 on a question it is supposed to be
    # unable to answer, because case is not the hard part.
    same = set(rg("-l", "-F", "-w", name, cwd=root)) | set(rg("-l", "-F", "-iw", name, cwd=root))
    other: set[str] = set()
    for spell in (SPELLINGS[1], SPELLINGS[2]):
        try:
            written = spell(name)
        except IndexError:
            continue
        # Only forms that removed a separator. `MAX_RETRIES` differs from
        # `max_retries` by case alone and `rg -i` bridges it; `MaxRetries`
        # differs by structure and nothing a person types bridges that.
        if written and written.lower() != name.lower():
            other |= set(rg("-l", "-F", "-w", written, cwd=root))
    return same, other - same


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

BY_KEYWORD = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|final|async|export|pub)\s+)*"
    r"(?:class|def|func|function|type|struct|interface|module|fn)\s+(?:self\.)?"
    r"([A-Za-z_][A-Za-z0-9_]{4,})"
)
"""`class Widget`, `def cleanup_database`, `fn read_all`. No trailing
punctuation required: Ruby writes a method with no parentheses at all."""

BY_SHAPE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|final|async|export|override|const|let|var)\s+)+"
    r"(?:[A-Za-z_][\w<>\[\],.]*\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]{4,})\s*[(=]"
)
"""`public void processRequest(`, `export const useThing =`. A modifier is
required and so is the `(` or `=`, because without both this matches any
sentence with two words in it."""

BY_RECEIVER = re.compile(r"^\s*func\s+\([^)]*\)\s*([A-Za-z_][A-Za-z0-9_]{4,})")
"""`func (s *Server) HandleRequest(`, where Go puts the name after the
receiver — which is most of the methods in a Go codebase."""

DEFINERS = (BY_KEYWORD, BY_SHAPE, BY_RECEIVER)
"""Three forms, because one was a sample nobody chose.

The first version took only `keyword Name` and so could not see a Go
method on a receiver, a Java or C# method, a TypeScript arrow export or
a Ruby singleton — which is most of the definitions in the two largest
workspaces in this corpus, both of which are Go and C#. Subjects are
drawn from the *tree*, never from what the tool returned: asking a
search engine about the names it chose to show is a measurement grading
itself."""


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
                for shape in DEFINERS:
                    match = shape.match(line)
                    if match:
                        found.add(match.group(1))
                        break
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
        answer = thulr("why", symbol, cwd=home, env=env)
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


def defining_files(name: str, root: Path, repos: list[str]) -> set[str]:
    """Files where this name is *defined*, by the same reading that chose it.

    Structural, and that is the whole repair. Ground truth used to be
    "files ripgrep finds naming this", which is what the control
    computes — so the control was right by construction and could not
    lose. Three attempts at fixing the *scoring* all failed for that
    reason; the question had to change instead.
    """
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
                if any((m := shape.match(line)) and m.group(1) == name for shape in DEFINERS):
                    found.add(f"{repo}/{path.relative_to(root / repo)}")
                    break
    return found


WHY_NO_SETTING_QUESTION = """`refs` on a setting, asked as "does it find the file that declares
this key", is not a question with a non-trivial answer and was removed.

The ground truth had to be "a key at the head of a line before a colon
or an equals sign" — which is character for character the rule
`link_extract._CONFIG_KEY` uses to build the edge. Measured that way it
scored 179 of 179, and that number says the pipeline delivers what the
extractor found, which is a tier-1 question. It was the fourth time this
harness graded a tool against its own rule, after crediting the control
for concision, for returning anything, and for a truth set that
contained it by construction.

The reason the mistake kept recurring is worth keeping: for "does it
find X", the natural ground truth is "where X is", and any rule written
to compute that tends to be one of the two tools' rules. The questions
that survive are the ones where the truth comes from somewhere else
entirely — git's own history for `why`, and for the spelling bridge a
set of files the control structurally cannot reach.

What is left of the settings claim is that bridge, `refs/spelling`,
which is measured and clean."""


def grade_refs(
    kind: str,
    subjects: list[str],
    root: Path,
    home: Path,
    env: dict[str, str],
    indexed: set[str],
    repos: list[str],
) -> list[Graded]:
    """Does it put the file that *defines* or *declares* this in reach?

    Both sides are graded by one rule — is a truth file among the first
    `DROWNED_AT` things this put in front of the reader — and neither can
    win by construction, because the truth is a position in a file that
    neither tool computed.
    """
    found: list[Graded] = []
    for subject in subjects:
        truth = defining_files(subject, root, repos)
        if not truth:
            continue
        answer = thulr("refs", subject, cwd=home, env=env)
        cited = [m.group(1) for m in (CITED.match(line) for line in answer.splitlines()) if m]
        cited = [c for c in cited if c and not c.startswith("commits/")]
        control = rg("-l", "-F", "-w", subject, cwd=root)
        found.append(
            Graded(
                kind,
                subject,
                bool(set(cited[:DROWNED_AT]) & truth),
                "found"
                if set(control[:DROWNED_AT]) & truth
                else "drowned"
                if set(control) & truth
                else "missed",
                reachable=bool(truth & indexed),
                control_count=len(control),
                detail=f"cited {len(cited)}, defines/declares in {len(truth)}",
            )
        )
    return found


def grade_spelling(
    subjects: list[str], root: Path, home: Path, env: dict[str, str], indexed: set[str]
) -> list[Graded]:
    """Does it reach code that spells a setting differently from its config?

    The one query the documents say `grep` cannot serve, asked so that
    the answer cannot come from the config file itself: only files using
    *another* spelling count. The control is given its best attempt —
    both `rg -w` and `rg -iw` on the spelling a person has in front of
    them — because a control that was never allowed to try is not one.
    """
    found: list[Graded] = []
    # Scanned rather than sampled, and stopped at `SAMPLE`: a key with a
    # structurally different spelling somewhere is rare — measured, a
    # sample of eighty keys yielded one — and a sample of one is not a
    # measurement. The order is still the frozen shuffle, so which ones
    # are reached is not a choice anybody made.
    for subject in subjects[: SAMPLE * 40]:
        if len(found) >= SAMPLE:
            break
        same, other = spelled_apart(subject, root)
        if not other:
            # Nothing spells it differently, so there is no bridge to
            # cross and the question is vacuous rather than failed.
            continue
        answer = thulr("refs", subject, cwd=home, env=env)
        cited = {m.group(1) for m in (CITED.match(line) for line in answer.splitlines()) if m}
        reached = set(rg("-l", "-F", "-w", subject, cwd=root)) | set(
            rg("-l", "-F", "-iw", subject, cwd=root)
        )
        found.append(
            Graded(
                "refs/spelling",
                subject,
                bool(cited & other),
                "found" if reached & other else "missed",
                reachable=bool(other & indexed),
                control_count=len(reached),
                detail=f"{len(other)} files spell it otherwise, {len(same)} as written",
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
    return names


DUPE_PAIR = re.compile(r"^\s+([0-9.]+)\s+(\S+?):(\d+)\s+<->\s+(\S+?):(\d+)")


def chunk_text(home: Path, where: str, line: int) -> str:
    """The stored text of the chunk at `repo/path:line`, or empty."""
    import lancedb

    repo, _, path = where.partition("/")
    table = lancedb.connect(str(home / ".thulr")).open_table("data")
    rows = (
        table.search()
        .where(
            f"repo = '{repo}' AND path = '{path.replace(chr(39), chr(39) * 2)}' "
            f"AND start_line = {line}"
        )
        .select(["text"])
        .limit(1)
        .to_arrow()
    )
    found = rows.column("text").to_pylist()
    return str(found[0]) if found else ""


def grade_dupes(home: Path, env: dict[str, str]) -> tuple[list[Graded], dict[str, Any]]:
    """Are the pairs `dupes` reports really the same code?

    No external ground truth exists for duplication, so this is the
    honest second best: recompute the similarity a different way. `dupes`
    compares token shingles; `difflib` compares character runs. Two
    measures that agree are evidence; one measure agreeing with itself is
    not.

    The sample size is stated because it has to be — a number without a
    denominator is not reported.
    """
    from difflib import SequenceMatcher

    out = thulr("dupes", "--limit", "200", cwd=home, env=env)
    pairs = [DUPE_PAIR.match(line) for line in out.splitlines()]
    found: list[Graded] = []
    boilerplate = 0
    for match in [m for m in pairs if m][:SAMPLE]:
        claimed = float(match.group(1))
        left = chunk_text(home, match.group(2), int(match.group(3)))
        right = chunk_text(home, match.group(4), int(match.group(5)))
        if not left or not right:
            continue
        agrees = SequenceMatcher(None, left, right).ratio()
        # What the pair is made of matters as much as whether it is real:
        # a licence header repeated in four hundred files is a true
        # duplicate and a useless report.
        lines = [x.strip() for x in left.splitlines() if x.strip()]
        prose = sum(1 for x in lines if x.startswith(("//", "#", "*", "/*")))
        imports = sum(1 for x in lines if x.startswith(("import", "require", "use ", "from ")))
        if lines and (prose + imports) / len(lines) > 0.6:
            boilerplate += 1
        found.append(
            Graded(
                "dupes",
                f"{match.group(2)}:{match.group(3)}",
                agrees >= 0.5,
                "n/a",
                detail=f"claimed {claimed:.2f}, difflib {agrees:.2f}",
            )
        )
    return found, {"sampled": len(found), "boilerplate": boilerplate}


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

    table = lancedb.connect(str(home / ".thulr")).open_table("data")
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
    env = {"THULR_CONFIG": str(home / "thulr.toml")}
    thulr("init", f"tier2-{org}", cwd=home, env=env)
    for repo in spec["repos"]:
        thulr("add-repo", repo["id"], str(root / repo["id"]), cwd=home, env=env)
    print(f"  indexing {org}", flush=True)
    thulr("index", cwd=home, env=env)

    indexed = indexed_paths(home)
    run = Run(org=org)
    run.notes["indexed_files"] = len(indexed)
    names = defined_names(root, repos)
    run.notes["names_in_tree"] = len(names)
    print(f"  why ({len(names)} names in the tree)", flush=True)
    run.graded += grade_why(root, repos, home, env, names[:SAMPLE])
    print("  refs on symbols", flush=True)
    run.graded += grade_refs(
        "refs/symbol", names[SAMPLE : SAMPLE * 2], root, home, env, indexed, repos
    )
    print("  refs on settings", flush=True)
    keys = config_keys(root)
    print("  refs across spellings", flush=True)
    run.graded += grade_spelling(keys, root, home, env, indexed)
    print("  dupes", flush=True)
    graded, notes = grade_dupes(home, env)
    run.graded += graded
    run.notes["dupes"] = notes
    # `deps` has no mechanical grading — whether an undeclared pair is a
    # real build problem or a fork sharing a vocabulary is a judgement,
    # and the methodology says to sample and say so rather than invent a
    # rule. The output goes into the protocol for a person to read.
    run.notes["deps"] = thulr("deps", "--limit", "8", cwd=home, env=env)
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


GATE = "the tool answers more than its control, significantly, on the reachable rows"

TOUCHES = {
    "why": "README `## Asking why, and who`; for-developers; for-agents",
    "refs/symbol": "README `refs` section; for-agents tool list",
    "refs/spelling": "README `refs` section; for-agents tool list",
}
"""Which documented claims each kind is evidence about.

Declared here rather than worked out after a run, so a protocol can say
what it bears on without anybody choosing that once the numbers are in.
It cannot say whether a claim is now wrong — that is a judgement — but
it can refuse to let one be quietly missed."""


def interpretation(runs: list[Run]) -> list[str]:
    """What the numbers say, mechanically, and where judgement begins.

    A generator cannot decide whether a result means a product should
    change. It can state the direction, whether the gate declared before
    the run was cleared, and what the run does not cover — and it can
    name the documents each kind is evidence about, so a claim is not
    quietly left standing. The methodology asks a protocol for an
    interpretation; this is the half a machine can be trusted with, and
    the rest is marked as needing a person.
    """
    every = [g for run in runs for g in run.graded]
    lines = ["", "## Interpretation", "", f"Gate: _{GATE}_.", ""]
    for kind in ("why", "refs/symbol", "refs/spelling"):
        live = [g for g in every if g.kind == kind and g.reachable]
        if not live:
            continue
        ours = sum(g.ours for g in live)
        theirs = sum(g.control == "found" for g in live)
        only_ours = sum(1 for g in live if g.ours and g.control != "found")
        only_rg = sum(1 for g in live if not g.ours and g.control == "found")
        p = mcnemar(only_ours, only_rg)
        # Always "ours N, control M", never a bare pair: a verdict whose
        # numbers have to be decoded is a verdict that will be misread.
        pairs = f"ours {only_ours}, control {only_rg}, p = {p:.4f}"
        if only_ours == only_rg:
            verdict = f"**tied** with its control ({pairs})"
        elif p >= 0.05:
            way = "ahead" if only_ours > only_rg else "behind"
            verdict = f"**{way}, not significantly** ({pairs})"
        elif only_ours > only_rg:
            verdict = f"**clears the gate** ({pairs})"
        else:
            verdict = f"**loses to its control** ({pairs})"
        unreachable = sum(1 for g in every if g.kind == kind and not g.reachable)
        lines += [
            f"- `{kind}`: {ours} of {len(live)} reachable against {theirs}; {verdict}."
            + (f" {unreachable} unreachable, excluded." if unreachable else ""),
            f"  Evidence about: {TOUCHES.get(kind, 'nothing documented')}.",
        ]
    lines += [
        "",
        "**What this does not say.** `why` is scored on the commits named for",
        "the definition it found, so a wrong definition is charged to `search`.",
        "Unreachable rows are counted out rather than in, because a file no",
        "grammar covers is a coverage failure and folding it in taxes every",
        "configuration equally and invisibly. Sample sizes are per workspace",
        "and stated in the table above; none of these is a population.",
        "",
        "**Needs a person.** Whether a commit named was the one a reader",
        "wanted, and whether any claim above should now change, are",
        "judgements this harness does not make.",
    ]
    return lines


def protocol(runs: list[Run], seconds: float) -> str:
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    every = [g for run in runs for g in run.graded]
    lines = [
        "# Tier 2 — is the answer right, and does it beat what a person would type?",
        "",
        f"_{time.strftime('%Y-%m-%d %H:%M')}, thulr `{sha}`, "
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
        for kind in ("why", "refs/symbol", "refs/spelling"):
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
    ]
    dupes = [g for run in runs for g in run.graded if g.kind == "dupes"]
    if dupes:
        agreed = sum(g.ours for g in dupes)
        boiler = sum(int(run.notes.get("dupes", {}).get("boilerplate", 0)) for run in runs)
        lines += [
            "",
            "## `dupes`, checked a second way",
            "",
            "No external ground truth exists for duplication, so the pairs it",
            "reports were re-scored with `difflib`, which compares character runs",
            "where `dupes` compares token shingles. Two measures agreeing is",
            "evidence; one measure agreeing with itself is not.",
            "",
            f"- **{agreed} of {len(dupes)}** sampled pairs reach 0.5 by the second measure.",
            f"- **{boiler} of {len(dupes)}** are mostly comment or import lines — true"
            " duplicates and useless ones, which is a different complaint from being"
            " wrong.",
        ]
    lines += [
        "",
        "## `deps`, for a person to read",
        "",
        "Whether an undeclared pair is a missing dependency or two repositories",
        "sharing a vocabulary is a judgement, not a rule, so this harness",
        "reports and does not grade.",
        "",
    ]
    for run in runs:
        said = str(run.notes.get("deps", "")).strip()
        if said:
            lines += [f"### `{run.org}`", "", "```", said, "```", ""]
    lines += interpretation(runs)
    lines += [
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
            "no ripgrep: set THULR_RG to its path. A tier-2 run without a "
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
        for kind in ("why", "refs/symbol", "refs/spelling"):
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
