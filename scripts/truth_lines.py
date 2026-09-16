"""Line-level truth for the harvested questions, derived from blame.

The questions say which *file* a fix changed, and every measurement
built on them grades a hit by file path. That was fine until it was
load-bearing: three chunking fixes in one day each changed zero
questions, not because they did nothing but because a file-level score
cannot see them. Moving prose from one chunk of a file into another
leaves the file in the same place in the ranking, by construction.

So the file is not enough, and the lines are recoverable without asking
anybody. The pull request number is in the question; GitHub writes it
into the commit subject — `(#1234)` when squashed, `Merge pull request
#1234` otherwise — so the fixing commit is findable in the clone. Blame
the file at the pinned commit and keep the lines that commit still owns:
if the fix survived to the state being indexed, that is exactly where
the answer lives now.

Where it did not survive — the lines were rewritten later — the question
gets no line truth and drops out of the line-level score rather than
being guessed at. That is 67 of 204 in the routine tier; the remaining
132 are enough to see a chunking change, which nothing before could.

Written to a sidecar rather than into the harvested files. Those are the
frozen record of what was asked, and this is derived from a repository
that keeps moving.

Usage:
    uv run python scripts/truth_lines.py
    uv run python scripts/truth_lines.py --org caddyserver
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import relevance as R  # noqa: E402

CORPUS = HERE / "acceptance_corpus"
LINES = CORPUS / "lines"


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        errors="replace",
        stdin=subprocess.DEVNULL,
    )
    return done.stdout


def fixing_commit(repo: Path, number: str) -> str | None:
    """The commit that closed this pull request, found in the clone.

    Two spellings, because GitHub writes two: a squash merge puts
    `(#1234)` at the end of the subject, and a merge commit says `Merge
    pull request #1234`. Fixed-string matching, since a number is not a
    pattern and `#` starts a comment in some of them.
    """
    for pattern in (f"(#{number})", f"pull request #{number}"):
        found = git(repo, "log", "--format=%H", "--all", "-F", f"--grep={pattern}").split()
        if found:
            return found[0]
    return None


def owned_lines(repo: Path, path: str, sha: str) -> list[int]:
    """Lines of `path` that `sha` still owns at the checked-out commit.

    `-l` for the long sha, so a prefix comparison cannot match the wrong
    commit. A line the fix wrote and somebody later rewrote belongs to
    the rewriter, and is correctly absent.
    """
    blame = git(repo, "blame", "-l", "--", path)
    return [n for n, line in enumerate(blame.splitlines(), 1) if line.startswith(sha)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", action="append")
    args = parser.parse_args()
    corpus = json.loads((CORPUS / "corpus.json").read_text(encoding="utf-8"))
    orgs = args.org or list(corpus)
    LINES.mkdir(parents=True, exist_ok=True)
    tally: Counter[str] = Counter()

    for org in orgs:
        path = CORPUS / "harvested" / f"{org}.json"
        if not path.is_file():
            continue
        root = R.materialise(org, corpus[org]["repos"])
        found: dict[str, dict[str, list[int]]] = {}
        for item in json.loads(path.read_text(encoding="utf-8"))["questions"]:
            tally["asked"] += 1
            number = item["source"]["pull"].rsplit("/", 1)[-1]
            per_file: dict[str, list[int]] = {}
            for answer in [item["truth"], *item.get("also_valid", [])]:
                repo_id, _, rel = answer.partition("/")
                repo = root / repo_id
                if not (repo / ".git").exists() or not (repo / rel).exists():
                    continue
                sha = fixing_commit(repo, number)
                if sha is None:
                    continue
                lines = owned_lines(repo, rel, sha)
                if lines:
                    per_file[answer] = lines
            if per_file:
                found[item["id"]] = per_file
                tally["with lines"] += 1
            else:
                tally["no surviving lines"] += 1
        out = LINES / f"{org}.json"
        out.write_text(json.dumps(found, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{org:<18}{len(found):>4} questions with line truth -> {out.name}", flush=True)

    print()
    for name, count in tally.most_common():
        print(f"  {name:<22}{count:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
