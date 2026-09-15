"""Tier 3, the version that measures fixing rather than finding.

`tier3.py` sends a fixed reading policy at each task and counts what it
had to read. That is honest about what it is — the size of the pile each
tool hands over — and it is not the question. The question is whether
somebody finishes the work with less of it.

So: a real agent, the same one on both sides, given a real issue and the
repository **as it stood before the fix**, and asked to fix it. One side
has wsindex over MCP and the other does not. Both keep every ordinary
tool, because a developer with wsindex still has grep and taking it away
would be measuring a straw man.

**What is graded.** The agent's diff against the diff the maintainers
actually merged, in the parent's line numbers so the two are comparable:
did it touch the same files, and did it touch the same lines. Not
"did the fix work" — that needs the project's own test suite, and
thirty-three repositories across seven languages do not have one this
can run. Said plainly rather than implied: this measures landing in the
right place, which is more than finding the file and less than fixing
the bug.

**What it costs.** Tokens, turns, wall clock and dollars, all reported
by the CLI itself, so the comparison is not an estimate.

Usage:
    uv run python scripts/tier3_agent.py --tasks 12
    uv run python scripts/tier3_agent.py --tasks 4 --org caddyserver

Environment:
    WSINDEX_RELEVANCE_DIR   corpus cache, shared with the other harnesses
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import relevance as R  # noqa: E402

CORPUS = HERE / "acceptance_corpus"
PROTOCOLS = HERE.parent / "docs" / "protocols"
BINARY = Path(sys.executable).parent / "wsindex"
CLAUDE = Path.home() / ".local" / "bin" / "claude"
SCRATCH = R.CACHE / ".tier3agent"
TRANSCRIPTS = SCRATCH / "transcripts"

SEED = 20260914
MAX_FILES = 2
"""Files the real fix may touch. More than two and "the same place" stops
being a place."""

TOOLS = ("Read", "Edit", "Write", "Glob", "Grep", "Bash")
"""What both sides get. The treatment adds wsindex over MCP and takes
nothing away: a developer with it still has grep, and removing grep
would measure a straw man rather than a tool.

Passed as `--tools`, not only as `--allowedTools`. The two are different
flags and the harness first used the wrong one: `--allowedTools` says
what may be run without asking, while `--tools` says what exists. With
only the former, every server configured on the operator's machine was
loaded as well — the first transcript shows **212 tools**, among them
this machine's mail and calendar — so the agent was working on somebody
else's repository with the operator's inbox on its belt, and both arms
carried two hundred tool definitions of system prompt that had nothing
to do with the question."""

WS_TOOLS = ("mcp__wsindex__search", "mcp__wsindex__refs", "mcp__wsindex__why")
"""Allowed on the treatment side only. Without this the server connects,
the tools are listed, and the first call stops for a permission that
nothing in a headless run can grant — which would have measured wsindex
by never letting it answer."""

ARMS = ("without", "legacy", "new")
"""Three arms in one run, because the agent's spread between runs is
wider than the effect being measured. The same twelve tasks gave the
**unchanged** control 36 743 mean tokens one evening and 51 415 the
next — a 40% swing on code nobody had touched — so a wording change
compared across two runs measures the evening. Here `legacy` and `new`
differ in nothing but the text the MCP server hands the agent, and
`without` has no wsindex at all: one evening, one task list, one model."""

LEGACY = SCRATCH / "legacy-src"
"""wsindex as committed, shadowing the editable install via PYTHONPATH.
The previous wording lives in git rather than behind a flag in the
shipped server, because an experiment should not leave scaffolding in
the product."""

PROMPT = """A user filed this issue against this repository:

    {title}

Find what causes it and fix it by editing the files in this working
directory. Make the smallest change that addresses the issue. Do not
write tests, do not commit, and do not explain at length — the edit is
the answer."""


@dataclass
class Attempt:
    """One agent run on one task."""

    files: tuple[str, ...] = ()
    lines: int = 0
    hit_file: bool = False
    hit_line: bool = False
    tokens: int = 0
    turns: int = 0
    seconds: float = 0.0
    cost: float = 0.0
    note: str = ""
    calls: dict[str, int] = field(default_factory=dict)
    """Tool name to how many times the agent called it. The first run of
    this harness kept only the totals, and when two tasks cost two and a
    half times more with the tool than without there was nothing to look
    at: whether a bad answer sent the agent wandering or it simply took a
    long road was a guess. It is not a guess now."""

    transcript: str = ""
    """Where the whole conversation was written. Outside the repository,
    in the corpus cache, because a transcript of somebody else's code is
    not ours to commit."""

    inventory: tuple[str, ...] = ()
    """Every tool the run actually had, as the agent reported at startup.
    Recorded because the harness once believed it was handing over six
    and was handing over 212, and nothing in the protocol could have
    shown it."""


@dataclass
class Task:
    org: str
    repo: str
    number: str
    title: str
    sha: str = ""
    truth: dict[str, set[int]] = field(default_factory=dict)
    attempts: dict[str, Attempt] = field(default_factory=dict)

    def arm(self, name: str) -> Attempt:
        """One arm's attempt, or an empty one if it never ran."""
        return self.attempts.get(name, Attempt())


def git(*args: str, cwd: Path) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    return done.stdout


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? ")


def touched(diff: str) -> dict[str, set[int]]:
    """Files and the parent-side lines a diff changes.

    Parent-side on purpose: both diffs here are against the same commit,
    so `-start,count` puts them in one coordinate system. Using the new
    side would compare line numbers from two different files.
    """
    found: dict[str, set[int]] = {}
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            found.setdefault(current, set())
        elif current and (hunk := HUNK.match(line)):
            start = int(hunk.group(1))
            count = int(hunk.group(2) or 1)
            found[current] |= set(range(start, start + max(count, 1)))
    return {path: lines for path, lines in found.items() if lines}


def merge_sha(owner_repo: str, number: str) -> str | None:
    done = subprocess.run(
        ["gh", "api", f"repos/{owner_repo}/pulls/{number}", "--jq", ".merge_commit_sha"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    sha = done.stdout.strip()
    return sha or None


def run_agent(where: Path, title: str, mcp: Path | None, keep: Path) -> Attempt:
    """One headless agent, in one working tree, reporting its own bill.

    `stream-json` rather than `json`: the latter returns only the closing
    object, which is enough to bill a run and not enough to explain one.
    The stream carries the same closing object as its last `result`
    event — probed, not assumed — so the accounting is unchanged and the
    turns either side of it are now on disk.
    """
    allowed = [*TOOLS, *WS_TOOLS] if mcp is not None else list(TOOLS)
    argv = [
        str(CLAUDE),
        "-p",
        PROMPT.format(title=title),
        "--tools",
        ",".join(TOOLS),
        "--allowedTools",
        ",".join(allowed),
        # Only the server this harness passes. Without it the operator's
        # own servers join the run, which is neither the tool under test
        # nor anything the reader of a protocol would expect.
        "--strict-mcp-config",
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    if mcp is not None:
        argv += ["--mcp-config", str(mcp)]
    started = time.monotonic()
    done = subprocess.run(
        argv, cwd=where, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1800
    )
    seconds = round(time.monotonic() - started, 1)
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text(done.stdout, encoding="utf-8")

    said: dict[str, Any] = {}
    calls: dict[str, int] = {}
    inventory: tuple[str, ...] = ()
    for line in done.stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "result":
            said = event
        elif event.get("type") == "system" and event.get("subtype") == "init":
            inventory = tuple(sorted(str(name) for name in event.get("tools", [])))
        elif event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    name = str(block.get("name", "?"))
                    calls[name] = calls.get(name, 0) + 1
    if set(inventory) != set(allowed):
        print(
            f"    !! expected {len(allowed)} tools, the run had {len(inventory)}: "
            f"{sorted(set(inventory) ^ set(allowed))[:6]}",
            file=sys.stderr,
            flush=True,
        )
    if not said:
        return Attempt(
            seconds=seconds,
            note=f"no result event: {done.stderr.strip()[:120]}",
            calls=calls,
            transcript=keep.name,
            inventory=inventory,
        )
    usage = said.get("usage") or {}
    return Attempt(
        tokens=int(usage.get("input_tokens", 0))
        + int(usage.get("cache_creation_input_tokens", 0))
        + int(usage.get("output_tokens", 0)),
        turns=int(said.get("num_turns", 0)),
        seconds=seconds,
        cost=float(said.get("total_cost_usd") or 0.0),
        note=str(said.get("result", ""))[:120],
        calls=calls,
        transcript=keep.name,
        inventory=inventory,
    )


def grade(attempt: Attempt, where: Path, truth: dict[str, set[int]]) -> Attempt:
    """What the agent changed, against what the maintainers changed."""
    changed = touched(git("diff", "--unified=0", cwd=where))
    attempt.files = tuple(sorted(changed))
    attempt.lines = sum(len(v) for v in changed.values())
    attempt.hit_file = bool(set(changed) & set(truth))
    attempt.hit_line = any(changed.get(path, set()) & lines for path, lines in truth.items())
    return attempt


def prepare(org: str, repo: str, sha: str, label: str) -> Path | None:
    """A working tree at the commit before the fix."""
    source = R.CACHE / org / repo
    where = SCRATCH / f"{repo}-{sha[:7]}-{label}"
    shutil.rmtree(where, ignore_errors=True)
    git("worktree", "prune", cwd=source)
    subprocess.run(
        ["git", "worktree", "add", "--detach", "--force", str(where), f"{sha}^"],
        cwd=source,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return where if (where / ".git").exists() else None


def legacy_source() -> Path:
    """The committed wsindex source, for the arm with the old wording.

    `git archive` rather than a second checkout: only `mcp_server.py`
    differs from the working tree, so the two treatment arms are equal
    in everything except the sentences under test.
    """
    shutil.rmtree(LEGACY, ignore_errors=True)
    LEGACY.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "archive", "HEAD", "src/wsindex"],
        cwd=HERE.parent,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(["tar", "-x", "-C", str(LEGACY)], input=archive.stdout, capture_output=True)
    return LEGACY / "src"


def indexed(where: Path, *, shadow: Path | None = None) -> Path:
    """A wsindex workspace over this tree, and the MCP config for it.

    `shadow` puts another copy of the package ahead of the installed one
    on the server's PYTHONPATH — the seam the legacy arm runs through.
    """
    home = where.parent / f"{where.name}-index"
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "WSINDEX_CONFIG": str(home / "wsindex.toml")}
    for args in (("init", "tier3agent"), ("add-repo", "repo", str(where)), ("index",)):
        subprocess.run(
            [str(BINARY), *args],
            cwd=home,
            env=env,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=1800,
        )
    config = home / "mcp.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "wsindex": {
                        "command": str(BINARY),
                        "args": ["mcp"],
                        "env": {
                            "WSINDEX_CONFIG": str(home / "wsindex.toml"),
                            **({"PYTHONPATH": str(shadow)} if shadow else {}),
                        },
                    }
                }
            }
        )
    )
    return config


def pick(orgs: list[str], wanted: int, only: set[str], seed: int) -> list[Task]:
    """Tasks whose real fix is small enough to have a place.

    `only` names tasks as `repo#number` and exists to re-ask one that
    already ran — it does not touch the selection rule, because with no
    `only` the shuffle, the seed and the count are what they were.
    """
    found: list[Task] = []
    corpus = json.loads((CORPUS / "corpus.json").read_text(encoding="utf-8"))
    entries: list[tuple[str, dict[str, Any]]] = []
    for org in orgs:
        path = CORPUS / "harvested" / f"{org}.json"
        if not path.is_file():
            continue
        R.materialise(org, corpus[org]["repos"])
        entries += [(org, q) for q in json.loads(path.read_text(encoding="utf-8"))["questions"]]
    random.Random(seed).shuffle(entries)
    for org, item in entries:
        if not only and len(found) >= wanted:
            break
        answers = [item["truth"], *item.get("also_valid", [])]
        if not 1 <= len(answers) <= MAX_FILES:
            continue
        repo = item["truth"].split("/")[0]
        owner_repo = item["source"]["pull"].removeprefix("https://github.com/").split("/pull/")[0]
        number = item["source"]["pull"].rsplit("/", 1)[-1]
        if only and f"{repo}#{number}" not in only:
            continue
        sha = merge_sha(owner_repo, number)
        if not sha:
            continue
        source = R.CACHE / org / repo
        diff = git("diff", "--unified=0", f"{sha}^", sha, cwd=source)
        # Keyed by the path as the diff spells it. The first version
        # stripped a leading segment on the assumption that a repository
        # name was in front of it — there is none in `git diff` inside a
        # repository — so every truth key was mangled and the first task
        # scored a miss on both sides while the agent had in fact edited
        # the right file.
        truth = {
            path: lines for path, lines in touched(diff).items() if f"{repo}/{path}" in answers
        }
        if not truth:
            continue
        found.append(
            Task(org=org, repo=repo, number=number, title=item["text"], sha=sha, truth=truth)
        )
        print(f"  task {repo}#{number}: {len(truth)} file(s)", flush=True)
    return found


def summarise(calls: dict[str, int]) -> str:
    """Tool use as one line, busiest first."""
    if not calls:
        return "no tools"
    order = sorted(calls.items(), key=lambda kv: (-kv[1], kv[0]))
    return " ".join(f"{short(name)}:{count}" for name, count in order)


def short(name: str) -> str:
    """`mcp__wsindex__search` is `ws:search`; everything else is itself."""
    return "ws:" + name.split("__")[-1] if name.startswith("mcp__wsindex__") else name


def protocol(tasks: list[Task], seconds: float) -> str:
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    def tally(arm: str) -> dict[str, Any]:
        runs = [t.arm(arm) for t in tasks]
        done = [r for r in runs if r.files]
        n = max(len(runs), 1)
        return {
            "file": sum(r.hit_file for r in runs),
            "line": sum(r.hit_line for r in runs),
            "edited": len(done),
            "tokens": sum(r.tokens for r in runs) // n,
            "turns": sum(r.turns for r in runs) // n,
            "cost": sum(r.cost for r in runs),
            "seconds": sum(r.seconds for r in runs) / n,
            "tools": next((r.inventory for r in runs if r.inventory), ()),
        }

    counts = {arm: tally(arm) for arm in ARMS}
    calls = {arm: calls_for(tasks, arm) for arm in ARMS}

    def row(label: str, key: str, fmt: str = "{}") -> str:
        return f"| {label} | " + " | ".join(fmt.format(counts[a][key]) for a in ARMS) + " |"

    lines = [
        "# Tier 3, with an agent — does it finish the work with less?",
        "",
        f"_{time.strftime('%Y-%m-%d %H:%M')}, wsindex `{sha}`, {len(tasks)} tasks, "
        f"{seconds / 60:.0f} min._",
        "",
        "## Conditions",
        "",
        "- One real agent, the same on all three arms, given a real issue and",
        "  the repository **at the commit before the fix**.",
        "- Every arm keeps every ordinary tool; two of them add wsindex over",
        "  MCP and take nothing away — a developer with it still has grep.",
        "- `legacy` and `new` differ in **nothing but the wording** the MCP",
        "  server gives the agent. Same index, same code, same evening.",
        "- Graded against the diff the maintainers merged, in the parent's",
        "  line numbers so the two are comparable.",
        "- Tools each arm actually had, as the agent reported at startup: "
        + ", ".join(f"{a} **{len(counts[a]['tools'])}**" for a in ARMS)
        + ".",
        "",
        "## The gate, declared before the run",
        "",
        "`new` lands on the same lines at least as often as `without` and",
        "spends fewer tokens; and it beats `legacy`, which is the same tool",
        "described the old way — otherwise the wording changed nothing and",
        "the difference was the evening.",
        "",
        "## Results",
        "",
        "| | " + " | ".join(ARMS) + " |",
        "| --- | " + " | ".join("---:" for _ in ARMS) + " |",
        row("same file", "file", "{} of " + str(len(tasks))),
        row("**same lines**", "line", "**{}**"),
        row("edited anything", "edited"),
        row("mean tokens", "tokens"),
        row("mean turns", "turns"),
        row("mean seconds", "seconds", "{:.0f}"),
        row("total cost", "cost", "${:.2f}"),
        "",
        "**What this does not say.** Whether the fix *works* is not measured:",
        "that needs the project's own tests, and thirty-three repositories",
        "across seven languages do not have a suite this can run. Landing on",
        "the same lines is more than finding the file and less than fixing",
        "the bug, and the gap between those is the agent's judgement, which",
        "is the same on every arm here.",
        "",
        "## What the agent actually called",
        "",
        "Mean calls per task. The question this answers is whether the",
        "treatment *replaced* any reading or merely added to it — the first",
        "run of this harness found wsindex called once a task on top of an",
        "unchanged amount of grep, which costs and saves nothing.",
        "",
        "| Tool | " + " | ".join(ARMS) + " |",
        "| --- | " + " | ".join("---:" for _ in ARMS) + " |",
    ]
    every = {name for arm in ARMS for name in calls[arm]}
    for name in sorted(every, key=lambda n: -sum(calls[a].get(n, 0.0) for a in ARMS)):
        lines.append(
            f"| `{name}` | " + " | ".join(f"{calls[a].get(name, 0.0):.1f}" for a in ARMS) + " |"
        )
    lines += [
        "",
        "## Raw rows",
        "",
        "Transcripts are kept beside the corpus cache, not in this repository.",
        "",
        "| Task | " + " | ".join(f"{a}: file/line | tokens" for a in ARMS) + " | issue |",
        "| --- | " + " | ".join("--- | ---:" for _ in ARMS) + " | --- |",
    ]
    for t in tasks:
        cells = []
        for arm in ARMS:
            a = t.arm(arm)
            cells.append(
                f"{'yes' if a.hit_file else 'no'}/{'yes' if a.hit_line else 'no'} | {a.tokens}"
            )
        lines.append(f"| `{t.repo}#{t.number}` | " + " | ".join(cells) + f" | {t.title[:50]} |")
    lines += [
        "",
        "### Tool use, per task",
        "",
        "| Task | " + " | ".join(ARMS) + " |",
        "| --- | " + " | ".join("---" for _ in ARMS) + " |",
    ]
    for t in tasks:
        lines.append(
            f"| `{t.repo}#{t.number}` | "
            + " | ".join(summarise(t.arm(a).calls) for a in ARMS)
            + " |"
        )
    return "\n".join(lines) + "\n"


def calls_for(tasks: list[Task], arm: str) -> dict[str, float]:
    """Mean calls per task, per tool, for one arm."""
    total: dict[str, float] = {}
    for task in tasks:
        for name, count in task.arm(arm).calls.items():
            total[short(name)] = total.get(short(name), 0.0) + count
    return {name: value / max(len(tasks), 1) for name, value in total.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=12)
    parser.add_argument("--org", action="append")
    parser.add_argument(
        "--only",
        action="append",
        metavar="REPO#NUMBER",
        help="re-ask named tasks instead of drawing new ones",
    )
    parser.add_argument("--suffix", default="", help="tag the protocol filename")
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help="draw a different task list; the default is the frozen one",
    )
    args = parser.parse_args()
    if not CLAUDE.is_file():
        print(f"no agent at {CLAUDE}", file=sys.stderr)
        return 2
    corpus = json.loads((CORPUS / "corpus.json").read_text(encoding="utf-8"))
    orgs = args.org or [o for o, c in corpus.items() if c["tier"] == "routine"]
    SCRATCH.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    shadow = legacy_source()
    print("choosing tasks", flush=True)
    tasks = pick(orgs, args.tasks, set(args.only or ()), args.seed)
    if args.only and not tasks:
        print(f"no task matched {sorted(set(args.only))}", file=sys.stderr)
        return 2
    for n, task in enumerate(tasks, start=1):
        print(f"[{n}/{len(tasks)}] {task.repo}#{task.number}", flush=True)
        for arm in ARMS:
            where = prepare(task.org, task.repo, task.sha, arm)
            if where is None:
                continue
            mcp = (
                None
                if arm == "without"
                else indexed(where, shadow=shadow if arm == "legacy" else None)
            )
            keep = TRANSCRIPTS / f"{task.repo}-{task.number}-{arm}.jsonl"
            attempt = grade(run_agent(where, task.title, mcp, keep), where, task.truth)
            task.attempts[arm] = attempt
            print(
                f"    {arm:<8} file={attempt.hit_file} line={attempt.hit_line} "
                f"{attempt.tokens} tokens ${attempt.cost:.2f}  {summarise(attempt.calls)}",
                flush=True,
            )
    PROTOCOLS.mkdir(parents=True, exist_ok=True)
    out = PROTOCOLS / f"tier3-agent-{time.strftime('%Y-%m-%d')}{args.suffix}.md"
    out.write_text(protocol(tasks, time.monotonic() - started), encoding="utf-8")
    print(f"\nprotocol written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
