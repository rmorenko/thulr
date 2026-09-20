"""Tier 1: does every command run, and is what it says true?

The first of the three tiers in `docs/design/test-methodology.md`, and
the one the unit suite cannot cover. A unit test proves a function
returns what its author expected of a fixture. This drives the shipped
binary over a real workspace and checks the *claims* — that the file and
line a search cites really hold the text it showed, that a run which
reports success actually read the repository, that an index still
answers the same questions after being compacted.

Those are the failures the field trial found and the suite did not: two
crashes on real corpora, and three workspaces that indexed seven per cent
of their files and said nothing.

A check here fails in one of three ways, and they are recorded apart
because they mean different things:

- **crash** — the command did not finish.
- **false** — it finished and what it printed is not true of the
  workspace.
- **silent** — it finished, what it printed is true, and it withheld
  something a person needed. Silence where a warning belongs is the
  failure mode this project has been bitten by most.

Usage:
    uv run python scripts/tier1.py                 # smallest workspace
    uv run python scripts/tier1.py caddyserver     # a named one
    uv run python scripts/tier1.py --all           # every workspace

Environment:
    THULR_RELEVANCE_DIR   corpus cache, shared with relevance.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "acceptance_corpus"
CACHE = Path(os.environ.get("THULR_RELEVANCE_DIR", Path.home() / ".cache" / "thulr-relevance"))
PROTOCOLS = HERE.parent / "docs" / "protocols"

SMALLEST = "DatabaseCleaner"
"""The default workspace: 87 files, indexes in seconds. Tier 1 asks
whether a command is honest, and honesty does not need a large corpus —
the tiers that do are 2 and 3."""

BINARY = Path(sys.executable).parent / "thulr"
"""The installed console script, beside the interpreter running this."""

TIMEOUT = 1800.0
"""Per command. Generous because `index` on a large workspace is
minutes, and a timeout that fires is recorded as a crash rather than
retried."""


@dataclass
class Check:
    """One claim, put to the shipped binary.

    Attributes:
        command: What was run, for the protocol.
        claim: What it is supposed to be true of.
        ok: Whether it held.
        how: `pass`, `crash`, `false` or `silent` — see the module
            docstring for why the three failures are not one.
        detail: Enough to act on without re-running.
        seconds: What it cost.
    """

    command: str
    claim: str
    ok: bool
    how: str
    detail: str = ""
    seconds: float = 0.0


@dataclass
class Run:
    org: str
    checks: list[Check] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)


def thulr(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """One invocation of the real CLI, never of an import.

    A subprocess against the installed entry point, not an import and
    not `-m`: tier 1 is about the thing that ships, and importing the
    package would skip argument parsing, the composition root, and every
    way a command can fail before it reaches its body. `-m` was tried
    first and does not work — there is no `__main__` — which is itself
    worth knowing about the package.
    """
    return subprocess.run(
        [str(BINARY), *args],
        cwd=cwd,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=TIMEOUT,
    )


def timed(fn: Any) -> tuple[Any, float]:
    started = time.monotonic()
    return fn(), round(time.monotonic() - started, 2)


CITATION = re.compile(r"^\s*(\S+?):(\d+)(?:-(\d+))?\b")


def check_citations(text: str, root: Path, repos: set[str]) -> tuple[int, list[str]]:
    """Do the `repo/path:line` a command printed exist on disk?

    The strongest claim any of these commands makes and the cheapest to
    verify: a citation that points at a line a file does not have is a
    wrong answer no amount of ranking fixes, and an index that has
    drifted from the tree produces exactly that.
    """
    bad: list[str] = []
    seen = 0
    for line in text.splitlines():
        found = CITATION.match(line)
        if not found:
            continue
        where, first = found.group(1), int(found.group(2))
        repo, _, rel = where.partition("/")
        if repo not in repos or not rel:
            continue
        if rel.startswith("commits/"):
            # A commit chunk's path is synthetic — `commits/<date>-<sha>`
            # — and names no file on disk. Checking it as one is a bug in
            # this harness, not in the answer.
            continue
        seen += 1
        path = root / repo / rel
        if not path.is_file():
            bad.append(f"{where}:{first} — no such file")
            continue
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError as exc:
            bad.append(f"{where}:{first} — unreadable ({exc})")
            continue
        if not 1 <= first <= len(lines):
            bad.append(f"{where}:{first} — file has {len(lines)} lines")
    return seen, bad


def run_workspace(org: str, spec: dict[str, Any]) -> Run:
    """Every tier-1 check against one pinned workspace."""
    sys.path.insert(0, str(HERE))
    import relevance as R

    root = R.materialise(org, spec["repos"])
    repos = {repo["id"] for repo in spec["repos"]}
    home = CACHE / ".tier1" / org
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)
    env = {"THULR_CONFIG": str(home / "thulr.toml"), "PYTHONPATH": str(HERE.parent / "src")}
    run = Run(org=org)

    def record(command: str, claim: str, fn: Any) -> Check:
        outcome, seconds = timed(fn)
        ok, how, detail = outcome
        check = Check(command, claim, ok, how, detail, seconds)
        run.checks.append(check)
        print(f"  {'ok ' if ok else how.upper():<7} {command:<28} {detail[:70]}", flush=True)
        return check

    # --- setup ------------------------------------------------------
    def do_init() -> tuple[bool, str, str]:
        done = thulr("init", f"tier1-{org}", cwd=home, env=env)
        if done.returncode != 0:
            return False, "crash", done.stderr.strip()[:400]
        exists = Path(env["THULR_CONFIG"]).is_file()
        return exists, "pass" if exists else "false", "config written" if exists else "no config"

    record("init", "writes a config it can read back", do_init)

    def do_add() -> tuple[bool, str, str]:
        for repo in spec["repos"]:
            done = thulr("add-repo", repo["id"], str(root / repo["id"]), cwd=home, env=env)
            if done.returncode != 0:
                return False, "crash", f"{repo['id']}: {done.stderr.strip()[:300]}"
        shown = thulr("status", cwd=home, env=env).stdout
        missing = [r for r in repos if r not in shown]
        return (not missing), "pass" if not missing else "false", f"missing from status: {missing}"

    record("add-repo", "every repo appears in status", do_add)

    # --- the corpus -------------------------------------------------
    def do_index() -> tuple[bool, str, str]:
        done = thulr("index", cwd=home, env=env)
        if done.returncode != 0:
            return False, "crash", done.stderr.strip()[:400]
        run.facts["index_stdout"] = done.stdout
        run.facts["index_stderr"] = done.stderr
        return True, "pass", done.stdout.strip().splitlines()[-1][:120] if done.stdout else ""

    record("index", "finishes on a real workspace", do_index)

    def do_coverage() -> tuple[bool, str, str]:
        """Did it read the tree, or say why not?

        Counted against **every** file in the tree, not against a list of
        suffixes this harness believes are indexable. That list was the
        first version and it could not see the failure it was written
        for: `pow-auth` holds 381 Elixir files, no grammar covers them,
        and a check whose denominator came from thulr's own supported
        suffixes scored it 30 of 36 — 83%, a pass — while 401 files went
        unread. A measurement that inherits the tool's blind spot cannot
        see the tool go blind.

        Reading little is not the failure. Reading little *in silence*
        is, so a low share passes when the run said so and names what it
        skipped.
        """
        on_disk = sum(
            1
            for repo in repos
            for path in (root / repo).rglob("*")
            if path.is_file()
            and not any(part.startswith(".") for part in path.relative_to(root).parts)
            and not {"node_modules", "vendor", "testdata"} & set(path.parts)
        )
        reported = 0
        for line in run.facts.get("index_stdout", "").splitlines():
            found = re.search(r"files:?\s+(\d+)", line)
            if found:
                reported = max(reported, int(found.group(1)))
        said = run.facts.get("index_stderr", "")
        warned = "matched no language" in said
        run.facts["files_on_disk"] = on_disk
        run.facts["files_reported"] = reported
        run.facts["warned_about_skips"] = warned
        if on_disk == 0:
            return True, "pass", "empty tree; nothing to claim"
        share = reported / on_disk
        if share >= 0.5:
            return True, "pass", f"{reported} of {on_disk} files ({share:.0%})"
        if warned:
            return True, "pass", f"{reported} of {on_disk} ({share:.0%}) and said which suffixes"
        return (
            False,
            "silent",
            f"{reported} of {on_disk} ({share:.0%}) and no word about the rest",
        )

    record("index", "reads the tree, or says why not", do_coverage)

    # --- the answers ------------------------------------------------
    def answering(command: str, *args: str) -> Any:
        def go() -> tuple[bool, str, str]:
            done = thulr(command, *args, cwd=home, env=env)
            if done.returncode != 0:
                return False, "crash", done.stderr.strip()[:400]
            seen, bad = check_citations(done.stdout, root, repos)
            if bad:
                return False, "false", f"{len(bad)} bad of {seen}: {bad[0]}"
            return True, "pass", f"{seen} citations, all resolve"

        return go

    record("search", "every file:line it cites exists", answering("search", "database cleaner"))
    a_file = next(
        (
            str(path)
            for repo in sorted(repos)
            for path in sorted((root / repo).rglob("*"))
            if path.is_file() and path.suffix in INDEXABLE
        ),
        "README.md",
    )
    record("explain", "answers about a real file", answering("explain", a_file))
    record("status", "runs on an indexed workspace", answering("status"))
    record("deps", "runs and cites nothing false", answering("deps"))
    record("dupes", "runs and cites nothing false", answering("dupes"))
    # `domains` is scoped to one repository by design and says so when a
    # workspace holds several, so it is asked the way it wants to be.
    record(
        "domains",
        "runs and cites nothing false",
        answering("domains", "--repo", sorted(repos)[0]),
    )
    record("stats", "runs", answering("stats"))

    def set_hybrid(on: bool) -> None:
        """Flip the one setting this pair of checks is about."""
        import tomli_w

        path = Path(env["THULR_CONFIG"])
        data = tomllib.loads(path.read_text())
        data.setdefault("store", {})["hybrid"] = on
        path.write_text(tomli_w.dumps(data))

    def do_monotone() -> tuple[bool, str, str]:
        """With one retrieval arm, is the score column monotone and on
        one scale?

        A person reads a ranked list top to bottom and reads the number
        beside each row as "how sure". A list whose numbers *rise* as it
        descends says the tool is broken even when the order is right.
        Asked with hybrid **off**, because with it on the list is ordered
        by agreement between arms and the column says so instead — which
        is what `do_plain` checks. A version of this that ran only in the
        fused configuration became unfalsifiable the moment the column
        stopped carrying numbers, and an unfalsifiable check is not one.
        """
        set_hybrid(False)
        done = thulr("search", "database cleaner", "-k", "10", cwd=home, env=env)
        set_hybrid(True)
        if done.returncode != 0:
            return False, "crash", done.stderr.strip()[:300]
        scores = [
            float(found.group(1))
            for line in done.stdout.splitlines()
            if (found := re.search(r"\s(\d+\.\d{3})\s", line))
        ]
        if len(scores) < 2:
            return True, "pass", "fewer than two scored rows; not applicable"
        rising = [f"{a} then {b}" for a, b in pairwise(scores) if b > a + 1e-9]
        off_scale = [s for s in scores if s > 1.0]
        if off_scale:
            return (
                False,
                "false",
                (
                    f"{len(off_scale)} of {len(scores)} scores above 1.0 "
                    f"(max {max(off_scale)}) — two scales in one column"
                ),
            )
        if rising:
            return False, "false", f"{len(rising)} rises in a ranked list: {rising[0]}"
        return True, "pass", f"{len(scores)} scores, monotone, all within [0, 1]"

    record("search", "with one arm, the score orders the list", do_monotone)

    def do_plain() -> tuple[bool, str, str]:
        """Whatever the column carries, every row must carry the same
        kind of thing. A list that mixes a similarity and a word is
        worse than either."""
        done = thulr("search", "database cleaner", "-k", "10", cwd=home, env=env)
        if done.returncode != 0:
            return False, "crash", done.stderr.strip()[:300]
        rows = [
            line.split()[1]
            for line in done.stdout.splitlines()
            if len(line.split()) > 2 and ":" in line.split()[0]
        ]
        kinds = {"number" if re.fullmatch(r"\d+\.\d+", r) else "word" for r in rows}
        if len(kinds) <= 1:
            return True, "pass", f"{len(rows)} rows, all {kinds or {'none'}}"
        return False, "false", f"the column mixes {kinds} down one list"

    record("search", "one kind of thing in the second column", do_plain)

    # --- the index survives being maintained ------------------------
    def do_compact() -> tuple[bool, str, str]:
        before = thulr("search", "database cleaner", "-k", "5", cwd=home, env=env).stdout
        done = thulr("compact", cwd=home, env=env)
        if done.returncode != 0:
            return False, "crash", done.stderr.strip()[:400]
        after = thulr("search", "database cleaner", "-k", "5", cwd=home, env=env).stdout
        same = before.strip() == after.strip()
        return (
            same,
            "pass" if same else "false",
            ("same answers after compaction" if same else "answers changed after compaction"),
        )

    record("compact", "does not change the answers", do_compact)

    def do_reindex() -> tuple[bool, str, str]:
        """An unchanged workspace must cost nothing and change nothing —
        the claim the README makes about incremental indexing."""
        before = thulr("search", "database cleaner", "-k", "5", cwd=home, env=env).stdout
        done, seconds = timed(lambda: thulr("index", cwd=home, env=env))
        if done.returncode != 0:
            return False, "crash", done.stderr.strip()[:400]
        after = thulr("search", "database cleaner", "-k", "5", cwd=home, env=env).stdout
        same = before.strip() == after.strip()
        run.facts["reindex_seconds"] = seconds
        return (
            same,
            "pass" if same else "false",
            (
                f"re-index took {seconds}s and "
                + ("changed nothing" if same else "CHANGED THE ANSWERS")
            ),
        )

    record("index", "re-running over an unchanged tree changes nothing", do_reindex)

    def do_repeatable() -> tuple[bool, str, str]:
        """The same question, asked twice, answered the same way.

        Nothing else here checks this, and every number this project
        publishes is from a single run. It is not hypothetical: a rebuilt
        BM25 index re-segments and breaks ties differently, which made a
        no-op re-index change the answers until it was found — by a
        different check, on one workspace, by luck.

        Three questions rather than one, because a tie only shows up
        where there are ties to break.
        """
        asked = ["database cleaner", "how does the connection get closed", "strategy"]
        for question in asked:
            first = thulr("search", question, "-k", "10", cwd=home, env=env).stdout
            again = thulr("search", question, "-k", "10", cwd=home, env=env).stdout
            if first != again:
                where = next(
                    (
                        n
                        for n, (a, b) in enumerate(
                            zip(first.splitlines(), again.splitlines(), strict=False), start=1
                        )
                        if a != b
                    ),
                    0,
                )
                return False, "false", f"`{question}` differs at line {where} between two asks"
        return True, "pass", f"{len(asked)} questions, identical answers twice"

    record("search", "the same question twice gives the same answer", do_repeatable)

    return run


INDEXABLE = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".kt",
    ".php",
    ".rb",
    ".vue",
    ".svelte",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".xml",
    ".md",
}
"""Suffixes worth asking `explain` about, and nothing more.

It used to be the coverage check's denominator, which made that check
blind to exactly the failure it exists for — see `do_coverage`."""


def protocol(runs: list[Run], seconds: float) -> str:
    """The run as a document, generated rather than typed."""
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    every = [c for run in runs for c in run.checks]
    failed = [c for c in every if not c.ok]
    lines = [
        "# Tier 1 — does every command run, and is what it says true?",
        "",
        f"_{time.strftime('%Y-%m-%d %H:%M')}, thulr `{sha}`, "
        f"{len(runs)} workspace(s), {len(every)} checks, {seconds:.0f}s._",
        "",
        "## Conditions",
        "",
        f"- Corpus: pinned, materialised under `{CACHE}`",
        f"- Workspaces: {', '.join(r.org for r in runs)}",
        "- Every command run as a subprocess against the shipped CLI",
        "",
        "## The gate, declared before the run",
        "",
        "Every check passes. A crash, a false claim or a silence where a",
        "warning belongs is a failure, and the three are recorded apart",
        "because they mean different things.",
        "",
        f"## Result: {len(every) - len(failed)} of {len(every)} passed",
        "",
        "| Workspace | Command | Claim | Outcome | Detail | s |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for run in runs:
        for check in run.checks:
            mark = "pass" if check.ok else f"**{check.how}**"
            lines.append(
                f"| `{run.org}` | `{check.command}` | {check.claim} | {mark} | "
                f"{check.detail[:120]} | {check.seconds} |"
            )
    if failed:
        lines += ["", "## What failed", ""]
        for check in failed:
            lines.append(f"- **{check.how}** `{check.command}` — {check.claim}. {check.detail}")
    lines += ["", "## Facts gathered", ""]
    for run in runs:
        readable = {k: v for k, v in run.facts.items() if not k.endswith(("stdout", "stderr"))}
        lines.append(f"- `{run.org}`: {json.dumps(readable, sort_keys=True)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    corpus = json.loads((CORPUS / "corpus.json").read_text(encoding="utf-8"))
    wanted = list(corpus) if "--all" in sys.argv else (args or [SMALLEST])
    started = time.monotonic()
    runs = []
    for org in wanted:
        print(f"{org}:", flush=True)
        runs.append(run_workspace(org, corpus[org]))
    seconds = time.monotonic() - started

    PROTOCOLS.mkdir(parents=True, exist_ok=True)
    out = PROTOCOLS / f"tier1-{time.strftime('%Y-%m-%d')}.md"
    out.write_text(protocol(runs, seconds), encoding="utf-8")
    failed = [c for run in runs for c in run.checks if not c.ok]
    print(f"\n{len(failed)} failed; protocol written to {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
