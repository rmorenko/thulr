"""Indexing and search pipeline: repos in, Hits out.

The pipeline sees only the VectorStore contract and works in plain text —
embedding is the store's private business. The concrete backend is built
at the edge (the CLI composition root) and injected through the
constructor; which repositories to index and with which metric comes from
`Config()`, read at call time. One process serves one workspace, so
threading those two values through the composition root only to hand them
back unchanged was ceremony.

This module is the engine and nothing else. What a run *produces* — its
tallies, its report, the rule that decides why a repo was read whole,
the shapes an answer comes back in — lives in `wsindex.run`, and is
re-exported from here so that no caller had to move when the two
separated. They separated when this file reached four roles and 992
lines, which is the threshold its own docstring had named one review
earlier.

`index` is incremental against git. Both of its paths — the
full pass and the incremental one — end in the same two lines: add the
chunks the working tree currently produces, then delete every stored
chunk in scope that it did not. Only the scope differs (a few changed
paths, or the whole dataset), which is why the reconciling delete is
written once. That also fixes the debt the full pass carried before
the store used to only ever add, so a file that shrank or vanished
left its old chunks in the index forever.
"""

import logging
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path

from wsindex.config import Config, Repository
from wsindex.ingest import (
    IndexState,
    RepoDiff,
    WalkedFile,
    chunk_file,
    diff_since,
    examine,
    has_uncommitted_changes,
)
from wsindex.ingest.commits import blame_links, blame_map, commit_chunks, read_commits
from wsindex.ingest.link_extract import links_for, occurrences_of
from wsindex.ingest.manifests import read_manifests
from wsindex.links import Edge, Link, LinkKind, LinkStore
from wsindex.model import Chunk, Hit, Kind, SearchFilter, SourceFile
from wsindex.rank.reranker import Reranker
from wsindex.rewrite.rewriter import Rewriter
from wsindex.run import (
    _WRITE_BATCH,
    Authorship,
    Definition,
    FileReport,
    FullPass,
    IndexReport,
    Reference,
    _blaming,
    _History,
    _selection,
    _Tally,
    _Totals,
    _unparsed,
    _why_full,
    _Written,
)
from wsindex.stats import SearchLog
from wsindex.store import VectorStore

_CANDIDATE_MULTIPLIER = 4

RERANK_BUDGET = 12
"""How many candidates per hit the reranker may be given, in total.

**In total, and that word is the whole constant.** Each dataset is asked
for `k * _CANDIDATE_MULTIPLIER` because the global top may sit entirely
in one repository, and every one of those used to be handed to the
reranker — so its cost scaled with the *number of repos*. A six-repo
workspace paid for 240 pairs to answer a `-k 10` search. Nobody decided
that; it fell out of the merge loop. Measured on this machine that is 11
seconds a search with a 568M reranker and 55 with a 1.5B one, and it is
what made the larger one ask MPS for a 32 GiB attention mask and die.

Twelve because the budget was swept, not picked, on the sixty blind
questions of `poe relevance` with a hosted reranker over an unchanged
local index — top-three / top-ten of the reachable answers:

| candidates at k=10 | identifier | descriptive | cross-repo | cost |
| --- | --- | --- | --- | --- |
| 40 (`k * 4`) | 13 / 14 | 4 / 8 | 2 / 5 | 294k tokens |
| **120 (`k * 12`)** | 13 / 15 | **8 / 11** | **4 / 5** | 884k |
| 240 (the old per-repo behaviour) | 13 / 15 | 7 / 12 | 3 / 5 | 1 397k |

Cutting at `k * 4` loses real answers: the reranker was promoting
candidates the bi-encoder had ranked below fortieth globally. Going wider
than this buys nothing and costs 58% more — more candidates is more
chances for the wrong one to score well.

Asked again on 2026-09-18 over a hosted embedder rather than a local
one, because that verdict was about a number and might have been about
the vectors under it. It was about the number: 120 / 240 / 320 candidates
answer 61, 62 and 62 of the 84 authored questions, one gained and none
lost, at 2.7 times the reranking. What the window holds is the limit and
widening it is not the way past: of 42 descriptive answers, 24 are inside
it and the reranker turns those into 21."""

COMMIT_SHARE = 0.2
"""How much of a result list history may take before it is crowding.

Commit messages and code sit in one vector space and are ranked by one
cosine, and they are not comparable on it: a message is prose, a query is
prose, so history scores well on almost anything. The field trial of
2026-09-11 watched that play out — on one workspace 89% of the index was
commit messages and 27 of 36 top-three slots went to them; asked about a
named constant in a Rust repository, all ten hits were commits, scored
within 0.005 of each other.

A fifth, and it is derived rather than chosen. Sweeping the cap from 0 to
10 across the sixty questions of `poe relevance`: **identifier questions
do not move at all** (9 of 20 at every cap — history neither helps nor
hurts them), while descriptive answers in the top ten go 4, 4, 4, 3, 1, 0
as the cap rises 0, 1, 2, 3, 5, 10. Two in ten is the largest value that
costs nothing, which is why it is not zero: filtering history out
entirely would buy the same answers and quietly delete a feature, since
a commit message is sometimes the honest answer to "why is this like
this".

The same sweep says the crowd is history specifically. Capping config
chunks alongside changed nothing at any combination."""

_QUOTA_MULTIPLIER = 3
"""How many candidates per hit the quota needs to have something to promote.

A cap without spares is a shorter list, not a better one: dropping four
commits out of ten leaves six. Three times k is enough for the worst case
measured — a top ten that was entirely history — and the store returning
thirty rows instead of ten is not what a search spends its time on."""

_AT_LINE = re.compile(r"^(?P<path>.+?):(?P<line>\d+)$")
"""A place rather than a name. Digits after the last colon are required,
so `Foo::bar` is still read as a symbol — which is what it is in Rust and
C++, and what somebody typing it means."""

_PER_FILE = 200
"""Chunks `why` will look at when asked about a line. A source file
holds tens; anything holding more than this is generated or minified."""

REFS_DEPTH = 200
"""Chunks the text arm of `refs` reads per repository.

Unbounded is what grep does and it is not what a reader wants: a name
used a thousand times answers "where is this used" with a thousand
lines, which is the drowning the ranked half of this tool exists to
avoid. Two hundred chunks is generous against the sizes measured here —
the largest workspace in the corpus holds 5 708 — and it is a cap that
can be seen in the code rather than a truncation nobody mentions."""

RETRIEVAL_WIDTH = 2
"""How much wider than the caller asked each arm retrieves.

`k` was doing two jobs — how deep to look and how much to return — and
they are not the same number. What comes back is what somebody then has
to read, so it should stay small; how far the arms reach before fusion
costs one store query and nothing a caller sees.

Measured by sweeping this and `FUSION_DEPTH` over 154 harvested
questions, which had never been done: the shipped setting came **31st of
36**. Retrieving at twice the requested depth and fusing ten times
deeper puts the answer in the top ten for 78 against 65 — 15 questions
gained, 2 lost, p = 0.0023 — and in the top three for 51 against 47.
The caller still gets `k`.

Not a lone spike: every combination reaching twice as wide scored 74 to
78, every one at the old width 55 to 75. The mechanism is visible in
that — deeper pools mean more disagreement between the arms, and
disagreement is what fusion has to work with."""

FUSION_DEPTH = 10
"""How many times the retrieval width the lexical arm fetches.

Fusion can only promote what an arm returned, and the whole point is
that the two arms disagree: measured on 154 harvested questions, the
answer was in the vector top ten for 55 and in ripgrep's output for 60,
with only 28 in both. Fetching just `k` from each would throw away most
of the disagreement before there was anything to fuse.

Was 5, on no measurement at all. See `RETRIEVAL_WIDTH` for the sweep
that set both."""

RRF_K = 60
"""The constant in reciprocal rank fusion, at its usual value.

Fusion by rank rather than by score, because the two arms have no common
scale — cosine similarity lives in [0, 1] and BM25 is unbounded and
corpus-dependent, so any weighted sum of them is a weight nobody can
justify. `1 / (RRF_K + rank)` needs no calibration and cannot be gamed
by one arm reporting large numbers."""


FOUND_BY = "found_by"
"""Metadata key: how many retrieval arms found this chunk.

Present only on a fused search. It is what a reader needs and the score
stopped being: under fusion the list is ordered by rank agreement, so a
hit with a lower cosine can and should sit above one with a higher, and
a column of cosines that does not descend reads as a broken sort."""


def _fuse(*arms: list[Hit]) -> list[Hit]:
    """Reciprocal rank fusion over one result list per retrieval arm.

    A chunk found by both arms outranks one found well by either, which
    is the property worth having here: the arms fail differently, so
    agreement is evidence and a single arm's confidence is not.

    Here rather than in the store, and that placement was learned by
    getting it wrong. Fused per dataset, every dataset's best hit gets
    the identical rank score, so the merge across datasets — which sorts
    by score — had nothing to order by. The contract already said so:
    merging and re-ranking across datasets is pipeline policy and lives
    in exactly one place.

    The returned `score` is a rank score and is not comparable to a
    cosine. Nothing downstream reads it as one: the quota counts kinds
    and the reranker replaces it outright.

    Args:
        arms: Result lists, each already best-first and each already
            merged across datasets.

    Returns:
        Every chunk any arm found, best fused rank first, each carrying
        the score retrieval gave it.
    """
    ranked: dict[tuple[str, str], float] = {}
    seen: dict[tuple[str, str], Hit] = {}
    # Which arms found each chunk, because that is what explains the
    # order and the score no longer does. A reader looking at a ranked
    # list asks "why is this one above that one"; under fusion the
    # answer is "both arms found it", and a cosine cannot say so.
    by: dict[tuple[str, str], list[int]] = {}
    for which, arm in enumerate(arms):
        for rank, hit in enumerate(arm, start=1):
            # Keyed by repo *and* id, not id alone. A chunk id is
            # `sha256(text, path)`, so two repositories holding the same
            # file hold the same id — which `dupes` exists because of —
            # and keying on it alone silently merges two real hits into
            # one. Found by a test that counted what the reranker was
            # given and got five where twelve were due.
            key = (str(hit.metadata.get("repo", "")), str(hit.native_id))
            ranked[key] = ranked.get(key, 0.0) + 1.0 / (RRF_K + rank)
            seen.setdefault(key, hit)
            by.setdefault(key, []).append(which)
    # Ordered by the fused rank, scored by what retrieval said. A rank
    # score is 0.016 for everything and would replace a similarity a
    # person can read with a number that is the same in every row — and
    # would make "an exact match scores 1.0" false everywhere it is
    # written down.
    return [
        replace(seen[key], metadata={**seen[key].metadata, FOUND_BY: len(set(by[key]))})
        for key in sorted(ranked, key=lambda key: ranked[key], reverse=True)
    ]


log = logging.getLogger(__name__)
"""Silent unless somebody attaches a handler; `wsindex serve` does.
What is logged here is what an operator asks about afterwards — which
repo was read, how much of it, how long, and what could not be read at
all. The CLI says the same things in its own words to a person who is
watching; a log is for the reader who was not."""


def _mentions_in_hit(
    name: str, hit: Hit, *, repo: str, seen: set[tuple[str, str, int]]
) -> list[Edge]:
    """Edges for one lexical hit, minus the lines already anchored.

    `seen` is read *and written* here, which is why it is a parameter
    rather than a return value: a name can appear twice in one chunk and
    once again in the next, and the second opinion must not report a
    line the link store already reported.
    """
    if hit.native_id is None:
        return []
    out: list[Edge] = []
    for line, via in occurrences_of(hit.text, name, start_line=hit.start_line):
        if (repo, hit.path, line) in seen:
            continue
        seen.add((repo, hit.path, line))
        out.append(
            Edge(
                kind=LinkKind.MENTIONS,
                name=name,
                line=line,
                chunk_id=hit.native_id,
                dst_chunk_id=None,
                url=None,
                via=via,
                repo=repo,
                path=hit.path,
            )
        )
    return out


@dataclass(frozen=True, kw_only=True)
class Pipeline:
    """The wired system: a store, plus whatever the current Config says.

    Frozen on purpose: a Pipeline is a bundle of dependencies, not state —
    nothing may accumulate between calls.

    Attributes:
        store: Any VectorStore backend; the pipeline never looks behind
            the contract.
        config: The workspace this pipeline indexes. A parameter rather
            than a `Config()` call inside the methods: the dependency is
            real either way, and a constructor that does not mention it
            is a constructor that lies. `Config` is a singleton, so the
            default is the same object the rest of the process sees — and
            a repo added at runtime is still picked up, because it is
            added to that object.
        state_dir: Where `index` keeps the per-repo "last indexed commit"
            file. Supplied by the composition root because it is a
            location, not a policy — the same reason the store gets its
            uri from there (see `wsindex.cli.build_pipeline`).
        reranker: Optional second stage of the search funnel. Present
            means `search` over-fetches candidates and re-scores them;
            None means the store's own ranking is the answer.
        rewriter: Optional stage *before* retrieval. Present means the
            question is also asked in the words the code is likely to
            use and the lists are fused; None means one query, as
            before. It sends the question and never any code — see
            `wsindex.rewrite`.
        stats: Where searches are recorded, or None to record nothing.
            Local by construction and by rule — see `wsindex.stats`.
        links: Where code-to-config edges are recorded, or None to skip
            link extraction entirely. When present, `index` writes the
            links a file yields and — this is the part that matters —
            deletes the links of every chunk it deletes (ADR-9).
    """

    store: VectorStore
    state_dir: Path
    config: Config = field(default_factory=Config)
    reranker: Reranker | None = None
    rewriter: Rewriter | None = None
    links: LinkStore | None = None
    stats: SearchLog | None = None

    def index(self, *, progress: Callable[[str], None] | None = None) -> IndexReport:
        """Index every repo into its own dataset (dataset name = repo id).

        Incremental against git: a repo goes down the fast path when it
        has been indexed before *and* its working tree is clean. Then only
        the files git reports as changed are read, and the chunks they no
        longer produce are deleted.

        Args:
            progress: Called with each repo id as that repo is reached,
                so a caller can show that silence is work. None keeps the
                run silent, which is what a pipe wants.

        A dirty working tree forces a full pass, and the run records no
        new commit for that repo. This is not pessimism, it is the only
        honest answer: a diff between two commits cannot see an
        uncommitted edit or an untracked file, but the full pass lists
        them (`ls-files --others`) and indexes both, so trusting the diff
        would leave the index describing a tree that never existed.
        Recording HEAD anyway would make the *next* run skip those same
        invisible changes forever.

        Decisions fixed here: files are read with errors="replace" so a
        stray non-UTF-8 file cannot abort the run; a repo whose directory
        does not exist goes to `missing_repos` and is skipped (an existing
        repo with zero indexable files is NOT missing).

        The new commit is recorded per repo, right after that repo's
        chunks are in the store — not once at the end. A crash halfway
        through a five-repo workspace must not cost the four that
        finished, and must not claim the one that did not.

        Returns:
            Totals across all repos; see IndexReport field docs.

        Raises:
            NotAGitRepositoryError: A configured repo is not a git
                repository root. Git-only is a decision: a
                fallback to plain walking would mean two models of
                state, so this is a config error with a message.
        """
        started = time.monotonic()
        config = self.config
        state = IndexState.load(self.state_dir)
        tally = _Tally()
        # Before anything is written, so `_prune_links` can tell which
        # definitions this run brought in. See there for why that matters.
        defined_before = self.links.anchor_names() if self.links is not None else set()
        for repo in config.repos:
            # The engine says *who* is being read; what to draw with that
            # is the caller's business (see `wsindex.ui`). A plain
            # callable rather than an event system: one caller, one fact.
            if progress is not None:
                progress(repo.id)
            state = self._pass_over(repo, state=state, tally=tally, config=config)
        self._prune_links(defined_before, written=tally.chunks > 0)
        # Once, after every repo, for the same reason the link prune is
        # here: the index covers the whole table and rebuilding it per
        # batch would make a run quadratic in batches. A store without a
        # lexical arm makes this a no-op.
        #
        # Only when something was written, and that is not an
        # optimisation. Rebuilding a BM25 index re-segments it, and a
        # re-segmented index breaks ties in a different order — so a run
        # that changed nothing changed the answers. Measured on an
        # 11 786-file workspace, where the number of ties makes it
        # visible; `for-agents.md` promises an agent replaying its own
        # run gets its own answers, and this is what kept that promise
        # from being true.
        refresh = getattr(self.store, "refresh_text_index", None)
        if refresh is not None and tally.chunks:
            refresh()
        log.info(
            "index finished in %.2fs: %d files, %d chunks",
            time.monotonic() - started,
            tally.files,
            tally.chunks,
        )
        return tally.report(seconds=round(time.monotonic() - started, 2))

    def _pass_over(
        self, repo: Repository, *, state: IndexState, tally: _Tally, config: Config
    ) -> IndexState:
        """One repository's turn, and the state it leaves behind.

        Lifted out of `index` whole rather than cut across: everything
        here is about *this* repo, and everything left behind in `index`
        is about the workspace. The returned state is the argument for
        the method existing — a commit is recorded per repo, right after
        that repo's chunks are in the store, so a crash halfway through a
        five-repo workspace costs the four that finished nothing.

        Returns:
            The state to carry into the next repo, updated only when this
            one both indexed and was clean.
        """
        root = Path(repo.path)
        if not root.is_dir():
            log.warning("skipping %s: %s does not exist", repo.id, root)
            tally.missing.append(repo.id)
            return state
        self.store.create_dataset(dataset_name=repo.id, metric=config.metric)
        diff, dirty = self._plan(repo, root=root, state=state)
        if diff.full:
            reason = _why_full(repo, state=state, dirty=dirty)
            log.info("full pass for %s: %s", repo.id, reason)
            tally.full.append((repo.id, reason))
        if diff.full or diff.changed or diff.deleted:
            self._write_repo(repo, root=root, diff=diff, config=config, tally=tally)
        # Nothing moved and nothing to reconcile: no read, no chunking,
        # no store round trip. That is the whole point of the step.
        if not dirty:
            # A clean tree is exactly `diff.head`, whether we got here by
            # a delta or by re-reading everything — so a first full pass
            # is what switches this repo onto the fast path. A dirty tree
            # records nothing: we indexed content that no commit
            # describes, and claiming HEAD would make the next run skip
            # those same changes forever.
            state = state.with_commit(repo.id, diff.head, markup=repo.markup_key)
            state.save(self.state_dir)
        self._manifest_links(repo, root=root)
        return state

    def _write_repo(
        self,
        repo: Repository,
        *,
        root: Path,
        diff: RepoDiff,
        config: Config,
        tally: _Tally,
    ) -> None:
        """Index one repo's changes and say what happened, at length."""
        totals = self._index_repo(repo, root=root, diff=diff, config=config)
        tally.add(repo.id, totals)
        log.info(
            "indexed %s: %d files, %d chunks, %d written, %d deleted",
            repo.id,
            totals.files,
            totals.chunks,
            totals.written,
            totals.deleted,
        )
        for path in totals.unreadable:
            log.warning("could not read %s/%s", repo.id, path)

    def _manifest_links(self, repo: Repository, *, root: Path) -> None:
        """Record what a repository publishes itself as and what it needs.

        Anchored to a synthetic source id rather than to a chunk,
        because these are facts about a *repository* and no chunk owns
        them — `go.mod` is not even indexed, the walker registers no
        `.mod` suffix. The id is stable per repo, so the delete below is
        the whole lifetime rule: a run replaces what the last one said.

        Args:
            repo: The repository being indexed.
            root: Its working tree.
        """
        if self.links is None:
            return
        source = f"manifest:{repo.id}"
        self.links.delete_by_source([source])
        found = read_manifests(root)
        entries = [(LinkKind.PROVIDES, name) for name in sorted(found.provides)]
        entries += [(LinkKind.DEPENDS_ON, name) for name in sorted(found.depends)]
        if not entries:
            return
        self.links.add_links(
            [Link(src_chunk_id=source, kind=kind, name=name, line=1) for kind, name in entries],
            repo=repo.id,
            path="(manifest)",
        )

    def _prune_links(self, defined_before: set[str], *, written: bool) -> None:
        """Drop mentions nothing defines, and say so if that cost anything.

        Two thirds of mentions name the standard library or a vendored
        package — 18 871 of caddyserver's 28 545 — and those can never be
        half of a join. They are dropped here rather than at write time
        because an extractor sees one file: "nothing defines this" is
        only true once every repo in the workspace has been read, which
        is exactly now.

        The risk it carries, and why the run says something out loud: a
        repo can join the workspace later and define a name whose
        mentions were already dropped. The files holding them have not
        changed, so nothing re-extracts them, and `refs` would answer
        with a definition and no uses — which reads as a fact about the
        code rather than as a gap in the index. `LinkStore.rescued` names
        that case exactly, and a full re-index is the repair.

        Args:
            defined_before: Normalised names the store already had
                definitions for when this run started.
            written: Whether this run wrote any links at all.
        """
        if self.links is None or not written:
            # Nothing was written, so nothing can have become unjoinable
            # and no definition can have arrived. The whole pass is
            # skippable, and skipping it is what keeps an unchanged
            # re-index the cheap thing the README says it is.
            return
        arrived = self.links.anchor_names() - defined_before
        lost = self.links.rescued(arrived)
        if lost:
            log.warning(
                "%d name(s) gained a definition whose uses were pruned earlier "
                "(%s%s) — run a full re-index to restore them",
                len(lost),
                ", ".join(sorted(lost)[:3]),
                ", ..." if len(lost) > 3 else "",
            )
        dropped = self.links.prune_unjoinable()
        if dropped:
            log.info("pruned %d mention(s) of names nothing in the workspace defines", dropped)

    def _plan(self, repo: Repository, *, root: Path, state: IndexState) -> tuple[RepoDiff, bool]:
        """Work out what to read for one repo, and whether HEAD describes it.

        Two separate questions, easy to conflate:

        - *Can a delta be trusted?* Only with a commit to diff from and a
          clean tree. Answered by `diff.full`, which the diff itself
          reports — a `since` that no longer resolves silently yields a
          full listing, and only `diff_since` knows that happened.
        - *May HEAD be recorded as indexed?* Whenever the tree is clean,
          full pass or not. This is what puts a freshly indexed repo onto
          the fast path for the next run.
        - *Is the markup the same one that produced the index?* A commit
          says nothing about which files the config selected from it.

        Returns:
            The diff to apply, and whether the working tree is dirty.
        """
        # Tracked edits, staged files and untracked files alike: any of
        # them makes the working tree differ from every commit, so no
        # commit-to-commit diff can describe what we are about to index.
        dirty = has_uncommitted_changes(root)
        # A third question, and the one a live run found missing: *is the
        # policy the same?* Editing `formats` changes which files this
        # tree produces while git reports nothing at all, so trusting the
        # commit alone made a markup change a silent no-op.
        remarked = state.markup.get(repo.id) != repo.markup_key
        since = None if dirty or remarked else state.commits.get(repo.id)
        return diff_since(root, since=since), dirty

    def _index_repo(
        self, repo: Repository, *, root: Path, diff: RepoDiff, config: Config
    ) -> _Totals:
        """Index what changed in one repo, then forget what it no longer holds.

        Four steps, in the only order they work in: decide what to read,
        note what the store holds now, write, subtract. Reading the
        stored ids *before* writing is what makes the last step mean
        "what was here when we started" — after the write the new ids
        would cancel out and the intent would be invisible.

        Args:
            repo: The repo being indexed; its id names the dataset.
            root: Repository root.
            diff: What to look at. `diff.full` widens the reconciling
                delete from "the paths listed here" to "the whole
                dataset", which is what makes a full pass also clean up
                files that vanished while nobody was watching.
            config: The workspace, for its reference templates.

        Returns:
            Totals for this repo.
        """
        picked = _selection(repo, root=root, changed=diff.changed, deleted=diff.deleted)
        scope = (
            None
            if diff.full
            else [*(walked.rel_path for walked in picked.indexable), *picked.forget]
        )
        stored = self.store.chunk_ids(dataset_name=repo.id, paths=scope)

        history = self._index_commits(repo, root=root, since=diff.since, config=config)
        files = self._index_files(
            repo, root=root, walked=picked.indexable, history=history, config=config
        )
        deleted = self._forget(repo, stale=sorted(stored - files.ids - history.ids))
        return _Totals(
            files=files.files,
            chunks=files.chunks,
            written=files.written,
            deleted=deleted,
            commits=history.written,
            unreadable=tuple(picked.unreadable),
            unparsed=files.unparsed,
            unclaimed=tuple(picked.unclaimed.most_common()),
        )

    def _index_commits(
        self, repo: Repository, *, root: Path, since: str | None, config: Config
    ) -> _History:
        """Index the repo's commit messages, and note where each one landed.

        Before the files, because blame edges point at these chunk ids
        and `git log` over a whole history costs milliseconds.
        """
        commits = read_commits(root, since=since, limit=config.max_commits)
        messages = commit_chunks(commits, repo=repo.id)
        # Keyed off the chunk's symbol rather than zipping: `commit_chunks`
        # drops commits with an empty message, so the two lists are not
        # guaranteed to line up.
        by_short = {message.symbol: message.id for message in messages}
        written = self.store.add_chunks(dataset_name=repo.id, chunks=messages)
        if self.links is not None and messages:
            # A commit message is where a ticket gets named, so the
            # outward references live here more than anywhere.
            self.links.add_links(
                links_for(messages, references=config.references),
                repo=repo.id,
                path="commits",
            )
        return _History(
            written=written,
            # Commit chunks are never stale: a commit is immutable, so
            # the chunk it produced can only be re-derived identically.
            # They still count as fresh, or a full pass — whose `stored`
            # covers the whole dataset — would reap every one of them.
            ids={message.id for message in messages},
            by_sha={c.sha: by_short[c.short] for c in commits if c.short in by_short},
        )

    def _index_files(
        self,
        repo: Repository,
        *,
        root: Path,
        walked: list[WalkedFile],
        history: _History,
        config: Config,
    ) -> _Written:
        """Chunk and link every file worth reading, writing in batches.

        A write per file is what this used to do, and it cost three ways
        at once. Each `add_chunks` asks the store which ids it already
        holds, so 149 files meant 149 round trips — 78% of an indexing
        run, more than chunking and writing together. Each also opens a
        Lance version, so the index carried 149 of them and took 4.4 MB
        where 1.7 was enough. And a fragmented index is slower to read:
        6.4 ms per search against 2.3 ms after compaction.

        Batching by chunk count rather than by repo keeps the memory
        bound a constant: a whole repo in flight is ~125 MB at 100k
        chunks, `_WRITE_BATCH` is a few megabytes.
        """
        totals = _Written()
        batch: list[Chunk] = []
        # Every blame at once rather than one per file in turn: they are
        # independent processes, and waiting for them one after another
        # was 83% of an indexing run.
        blames = (
            blame_map(root, [entry.rel_path for entry in walked]) if self.links is not None else {}
        )
        for entry in walked:
            source = SourceFile(repo=repo.id, path=entry.rel_path, lang=entry.lang, kind=entry.kind)
            with _blaming(repo.id, entry.rel_path):
                text = (root / entry.rel_path).read_text(encoding="utf-8", errors="replace")
                chunks: list[Chunk] = chunk_file(text, source)
                totals = totals.read(
                    chunks=len(chunks),
                    ids={chunk.id for chunk in chunks},
                    path=entry.rel_path if _unparsed(chunks) else None,
                )
                # Links are per file by nature — they name the file they
                # were found in — so they are recorded as the file is
                # read, not when its chunks happen to reach the store.
                self._link(
                    chunks,
                    source=source,
                    history=history,
                    references=config.references,
                    by_line=blames.get(entry.rel_path, {}),
                )
            batch += chunks
            if len(batch) >= _WRITE_BATCH:
                totals = totals.wrote(self.store.add_chunks(dataset_name=repo.id, chunks=batch))
                batch = []
        if batch:
            totals = totals.wrote(self.store.add_chunks(dataset_name=repo.id, chunks=batch))
        return totals

    def _link(
        self,
        chunks: list[Chunk],
        *,
        source: SourceFile,
        history: _History,
        references: dict[str, str],
        by_line: dict[int, str],
    ) -> None:
        """Record what one file's chunks name, and who wrote their lines.

        The repo id comes from `source`, which already carries it — a
        separate parameter for the same value is one more thing that can
        disagree with itself.
        """
        if self.links is None:
            return
        self.links.add_links(
            links_for(chunks, references=references), repo=source.repo, path=source.path
        )
        # Blame is the expensive half, so it is paid per *indexed* file —
        # which the incremental path already keeps down to what changed.
        self.links.add_links(
            blame_links(chunks=chunks, known=history.by_sha, by_line=by_line),
            repo=source.repo,
            path=source.path,
        )

    def _forget(self, repo: Repository, *, stale: list[str]) -> int:
        """Delete chunks the tree no longer produces, and their links.

        The same set, in the same breath. A link that outlives its chunk
        is not merely stale: it is indistinguishable from a real dangling
        link, so the drift report would fill with references from code
        that no longer exists (ADR-9).
        """
        if not stale:
            return 0
        deleted = self.store.delete_chunks(dataset_name=repo.id, ids=stale)
        if self.links is not None:
            self.links.delete_by_source(stale)
        return deleted

    def why(self, target: str, *, limit: int = 3) -> list[Definition]:
        """Definitions of `target`, each with the commits that wrote it.

        `target` is a symbol name, or a place — `src/thing.go:412`. The
        second spelling exists because it is how the question actually
        arrives: somebody is looking at a line they do not understand,
        and requiring them to first name the function that contains it
        asks them to do part of the lookup by hand. Measured across
        three agent runs on 48 tasks, `why` was called **at most once**,
        while `search` was called on nearly every task — the tool with
        the best number in this repository was the one nothing reached
        for, and needing a symbol first is the likeliest reason.

        Lives here because two adapters wanted it and each built it
        itself — `wsindex why` and the MCP tool — from the same three
        moves: find the definitions, walk their BLAMED_BY edges, fetch
        each commit's message. They had already drifted (one showed three
        definitions, the other all of them), which is what a rule in
        ADR-10 exists to prevent: an interface that cannot be written as
        a library call means the library is missing something.

        The `symbol` filter is a prefilter, so the store narrows to
        exactly the matching chunks and ranking only breaks ties among
        them.

        Args:
            symbol: Name to look for; matched as a substring.
            limit: How many definitions to return, best match first.

        Returns:
            The definitions, empty when nothing matches. A definition
            with no commits is normal — links may be off, or the repo
            may not have been indexed since blame edges existed.
        """
        place = _AT_LINE.match(target)
        found = (
            self._covering(place.group("path"), int(place.group("line")), limit)
            if place
            else self.search(target, k=limit, filters=SearchFilter(symbol=target))
        )
        if not found or self.links is None:
            return [Definition(hit=hit, commits=()) for hit in found]
        return [Definition(hit=hit, commits=tuple(self._authors(hit))) for hit in found]

    def _covering(self, path: str, line: int, limit: int) -> list[Hit]:
        """The indexed chunks that hold one line of one file, innermost first.

        Found through the path prefilter rather than by scanning every
        chunk's metadata: the filter narrows the store to one file, which
        is a handful of chunks, so the query text is only there because
        `search` needs one. A file with more chunks than `_PER_FILE` is a
        minified bundle, and `why` has nothing to say about those anyway.

        Innermost first — shortest span, named before unnamed — because a
        line sits inside a method inside a class, and the one somebody
        pointing at that line means is the smallest thing containing it.
        """
        wanted = path.lstrip("./")
        # The store keeps a path relative to its repository, so a caller
        # who pastes what the tool printed — `svc/client.py:4`, repo id
        # and all — filters on a string no row holds. Reported as "no
        # definition found", which is the wrong answer rather than a
        # narrow one, and it is the spelling a reader is most likely to
        # have in their clipboard.
        inside = next((r.id for r in self.config.repos if wanted.startswith(f"{r.id}/")), None)
        if inside is not None:
            wanted = wanted[len(inside) + 1 :]
        hits = self.search(wanted, k=_PER_FILE, filters=SearchFilter(path=f"*{wanted}"))
        covering = [
            hit for hit in hits if hit.path == wanted and hit.start_line <= line <= hit.end_line
        ]
        covering.sort(key=lambda hit: (hit.end_line - hit.start_line, hit.symbol is None))
        return covering[:limit]

    def _authors(self, hit: Hit) -> Iterator[Authorship]:
        """The commits a blame edge attributes this chunk to."""
        assert self.links is not None
        for edge in self.links.out_of([str(hit.native_id)], kind=LinkKind.BLAMED_BY):
            if edge.dst_chunk_id is None:
                yield Authorship(commit=edge.name, message=None)
                continue
            pointed = self.links.out_of([edge.dst_chunk_id], kind=LinkKind.REFERENCES)
            yield Authorship(
                commit=edge.name,
                message=self.commit_message(edge.repo, edge.dst_chunk_id),
                references=tuple(Reference(name=ref.name, url=ref.url) for ref in pointed),
            )

    def describe(self, path: Path) -> FileReport | None:
        """What the index knows about one file, or None if it owns none.

        `wsindex explain` in library terms. It used to do this itself,
        which cost the CLI eight imports out of `wsindex.ingest` and put
        real analysis — is this file parsed or merely windowed — in an
        adapter.

        Args:
            path: The file, absolute or relative to the current
                directory.

        Returns:
            The report, or None when the path lies outside every
            configured repo.
        """
        target = path.expanduser().resolve()
        for repo in self.config.repos:
            root = Path(repo.path).expanduser().resolve()
            if root != target and root not in target.parents:
                continue
            rel = target.relative_to(root).as_posix()
            found = examine(root, rel, ignore=repo.ignore, formats=repo.formats)
            if not isinstance(found, WalkedFile):
                return FileReport(repo=repo.id, rel_path=rel, skipped=found)
            return self._read_report(repo.id, target, found)
        return None

    @staticmethod
    def _read_report(repo_id: str, target: Path, found: WalkedFile) -> FileReport:
        """Chunk one file to see what it becomes; the second half of `describe`."""
        text = target.read_text(encoding="utf-8", errors="replace")
        source = SourceFile(repo=repo_id, path=found.rel_path, lang=found.lang, kind=found.kind)
        chunks = chunk_file(text, source)
        return FileReport(
            repo=repo_id,
            rel_path=found.rel_path,
            skipped=None,
            lang=found.lang,
            kind=found.kind,
            chunks=len(chunks),
            symbols=sum(1 for chunk in chunks if chunk.symbol),
            parsed_cleanly=not _unparsed(chunks),
        )

    def references(self, name: str) -> list[Edge]:
        """Every link that names this thing — a port, a ticket, a sha.

        A thin pass-through, and it earns its place by removing a
        second connection: the MCP tool opened its own `LinkStore` on
        every call, ignoring the one this Pipeline was handed. The
        resource was injected and then bypassed.

        Two arms, for the same reason `search` has two. The store holds
        the mentions it could anchor to a definition, which is the right
        rule for something that has to fit on a disk and the wrong one
        for the only source of an answer: measured on 240 symbol
        questions it found 124 where `rg -w` found 236, because anything
        defined in an unparsed file or outside the workspace has no
        anchor to keep it. The second arm reads the text index, which
        knows nothing about definitions and therefore misses none of
        them.

        They are complementary rather than redundant, which is what
        makes both worth running. The store bridges spellings —
        `max_retries` in a config against `MaxRetries` in the code — and
        BM25 cannot, since the two share no token. BM25 finds every
        plain occurrence, and the store only keeps the anchored ones.

        Args:
            name: Exactly as it was recorded — `8080`, `PROJ-412`.

        Returns:
            The edges, ordered by file then line; empty when links are
            switched off and no text index answers either.
        """
        stored = [] if self.links is None else self.links.by_name(name)
        return stored + self._mentions_in_text(name, stored)

    def _mentions_in_text(self, name: str, stored: list[Edge]) -> list[Edge]:
        """Occurrences the link store never anchored, read from the text.

        Skipped entirely without the text index, rather than falling back
        to a scan: this is a second opinion, and a `refs` that quietly
        takes minutes is worse than one that answers with what it has.
        """
        if not self.config.hybrid:
            return []
        seen = {(edge.repo, edge.path, edge.line) for edge in stored}
        found: list[Edge] = []
        for repo in self.config.repos:
            try:
                hits = self.store.lexical(dataset_name=repo.id, query=name, k=REFS_DEPTH)
            except (AttributeError, ValueError):
                continue  # a store without a text index, or a dataset with none
            for hit in hits:
                found.extend(_mentions_in_hit(name, hit, repo=repo.id, seen=seen))
        return sorted(found, key=lambda edge: (edge.repo, edge.path, edge.line))

    def commit_message(self, repo: str, chunk_id: str) -> str | None:
        """The text of one indexed commit message, or None if it is gone.

        A question about the workspace, answered here rather than by
        callers reaching through `pipeline.store` — which two of them
        did, each writing the same three lines. None is ordinary: a
        commit chunk that a later run re-indexed away is not an error.

        Args:
            repo: Repo id the commit belongs to.
            chunk_id: Id of the commit's own chunk, as a blame edge holds it.

        Returns:
            The message, or None when the store no longer has it.
        """
        return self.store.chunk_text(repo, ids=[chunk_id]).get(chunk_id)

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        repo: str | None = None,
        filters: SearchFilter | None = None,
    ) -> list[Hit]:
        """Global top-k across all config repos, best score first.

        With a rewriter configured the question is asked several ways and
        the lists are fused; without one this is exactly the single
        search it always was. See `wsindex.rewrite` for what that buys
        and what it sends.

        Args:
            query: Query text; embedding is the store's business.
            k: Maximum number of hits in the merged result.
            repo: Restrict to a single repo id; unknown id is an error,
                not a silent empty result.
            filters: Structural filters passed through to the store.

        Returns:
            At most k hits across all (scoped) repos, best first.

        Raises:
            ValueError: `repo` is set but not present in the config.
        """
        started = time.perf_counter()
        # The question always goes first and always goes: the arm that
        # replaced it with rewordings scored worse on every cut, and a
        # rewriter that returns nothing must leave search as it was.
        queries = [query, *(self.rewriter.rewrite(query) if self.rewriter else [])]
        lists = [self._one_query(q, k=k, repo=repo, filters=filters) for q in queries]
        best = lists[0] if len(lists) == 1 else _within_quota(_fuse(*lists), k=k)
        if self.stats is not None:
            self.stats.searched(
                query,
                k=k,
                repo=repo,
                hits=len(best),
                top_score=best[0].score if best else None,
                ms=round((time.perf_counter() - started) * 1000, 2),
                reranked=self.reranker is not None,
            )
        return best

    def _one_query(
        self,
        query: str,
        *,
        k: int = 10,
        repo: str | None = None,
        filters: SearchFilter | None = None,
    ) -> list[Hit]:
        """Global top-k across all config repos, best score first.

        Merge policy lives here and only here: every dataset is asked for
        k hits (the global top may sit entirely in one repo, so asking for
        less is wrong), then one stable sort merges and cuts to k — on
        equal scores the given repo order wins, which keeps results
        deterministic. A repo that was never indexed (store raises
        ValueError) contributes zero hits here: not yet indexed is a
        normal state, not an error. It is not a *silent* state, though —
        ask `unsearched()` and tell the reader, because an answer that
        skipped half the workspace must not look like one that did not.

        Repo scope is applied here (dataset list), structural filters go
        down to the store as a prefilter — reranker sees only the
        filtered candidates, so the funnel stays consistent (ADR-7).

        Args:
            query: Query text; embedding is the store's business.
            k: Maximum number of hits in the merged result.
            repo: Restrict to a single repo id; unknown id is an error,
                not a silent empty result.
            filters: Structural filters passed through to the store.

        Returns:
            At most k hits across all (scoped) repos, best score first.

        Raises:
            ValueError: `repo` is set but not present in the config.
        """
        repos = self._scope(repo)
        # Before reading, not after: a store holds the version it opened
        # at, so a long-lived process would answer from the corpus as it
        # was when it started and never fail doing it (ADR-10). Costs
        # ~4 ms; a CLI never notices and a server cannot do without it.
        self.store.refresh()
        n = _CANDIDATE_MULTIPLIER if self.reranker else _QUOTA_MULTIPLIER
        # How deep to look, which is not how much to return: everything
        # below still cuts to `k`, and only the reach changes.
        wide = k * RETRIEVAL_WIDTH
        all_hits: list[Hit] = []
        lexical: list[Hit] = []
        hybrid = self.config.hybrid
        for r in repos:
            try:
                hits = self.store.search(
                    dataset_name=r.id, query=query, k=wide * n, filters=filters
                )
            except ValueError:
                continue
            all_hits.extend(hits)
            if hybrid:
                lexical.extend(
                    self.store.lexical(
                        dataset_name=r.id, query=query, k=wide * FUSION_DEPTH, filters=filters
                    )
                )
        fused = bool(hybrid and lexical)
        if fused:
            # Each arm is ordered within itself first, because fusion
            # reads ranks: cosine is comparable across datasets (one
            # space) and so is BM25 (one index), so each list is
            # meaningful before the two meet.
            all_hits = _fuse(
                sorted(all_hits, key=lambda h: h.score, reverse=True),
                sorted(lexical, key=lambda h: h.score, reverse=True),
            )
        if self.reranker:
            # Merge, then cut, then re-score, and the order is the point:
            # cutting on the store's own score keeps the funnel's premise
            # intact — retrieval proposes, re-ranking disposes — while
            # bounding the expensive half. See `RERANK_BUDGET`.
            # Already in the order that matters when fused, and sorting
            # by score here would undo it: the score is a cosine again,
            # so this cut would hand the reranker the vector arm's top
            # candidates and throw the lexical half away before fusion
            # ever reached it. Measured when it did — top-three fell from
            # 50 to 32.
            ranked_first = (
                all_hits if fused else sorted(all_hits, key=lambda h: h.score, reverse=True)
            )
            candidates = ranked_first[: k * RERANK_BUDGET]
            scores = self.reranker.rank(query, [hit.text for hit in candidates])
            scored = [replace(h, score=s) for h, s in zip(candidates, scores, strict=True)]
            if fused:
                # A voter, not a dictator. Overwriting the score throws
                # the retrieval order away and keeps only the candidate
                # set, and measured that is a bad trade: of 29 questions
                # where fusion had put the answer *first*, re-scoring
                # kept it first for four and pushed four out of the top
                # ten entirely. Top-three went 45 to 36 for the whole
                # corpus. So the reranker joins the fusion instead, on
                # the same argument that chose fusion — three signals
                # that fail differently, and agreement is the evidence.
                all_hits = _fuse(candidates, sorted(scored, key=lambda h: h.score, reverse=True))
            else:
                all_hits = scored
        # Not re-sorted when fused: the order *is* the fusion, and
        # sorting by score would put the vector arm back in charge.
        ordered = all_hits if fused else sorted(all_hits, key=lambda h: h.score, reverse=True)
        return _within_quota(ordered, k=k)

    def _scope(self, repo: str | None) -> list[Repository]:
        """The repos a query covers, or a named error for an unknown id."""
        if repo is None:
            return list(self.config.repos)
        scoped = [r for r in self.config.repos if r.id == repo]
        if not scoped:
            raise ValueError(f"unknown repo id: {repo!r}")
        return scoped

    def fit(self, hits: list[Hit], *, budget: int) -> tuple[list[Hit], int]:
        """The longest prefix of `hits` that costs at most `budget` tokens.

        `k` answers "how many results"; an agent needs "how much context",
        and the two are not the same question. Ten hits are anywhere
        between two hundred tokens and twelve thousand depending on what
        they happen to contain, and today the caller finds out only after
        it has already spent them. Measured on the acceptance criteria,
        plain search fills a thousand tokens with fifteen chunks and
        already holds the expected answer for all ten queries — so this
        is not about finding more, it is about not overrunning.

        A prefix rather than a knapsack: hits arrive best-first, and
        skipping a large one to fit two small ones would quietly reorder
        relevance to save bytes. Dropping the tail is a decision the
        caller can see; re-ranking by size is not.

        Args:
            hits: What `search` returned, best first.
            budget: Maximum tokens the texts may cost together.

        Returns:
            The hits that fit, and what they cost. An empty list when even
            the first does not fit — the caller asked for less than one
            result is worth, and saying so beats overrunning silently.
        """
        kept: list[Hit] = []
        spent = 0
        for hit in hits:
            cost = self.store.count_tokens(hit.text)
            if spent + cost > budget:
                break
            kept.append(hit)
            spent += cost
        return kept, spent

    def unsearched(self, repo: str | None = None) -> tuple[str, ...]:
        """Configured repos the store has never heard of, in config order.

        The other half of `search`. A repo that was added to the config
        and never indexed — or whose indexing failed a month ago — takes
        no part in any search and says nothing about it, so every answer
        since has been quietly partial. This is what lets the caller put
        that in words.

        Asked separately rather than returned from `search` because a
        Pipeline is frozen and a search returns hits; the store call
        behind this reads one small registry table.

        Args:
            repo: Restrict to one repo id, matching the search it
                accompanies. An unknown id raises, exactly as it does
                there.

        Returns:
            The ids, in the order the config lists them; empty when the
            whole workspace is searchable.

        Raises:
            ValueError: `repo` is set but not present in the config.
        """
        known = self.store.datasets()
        return tuple(r.id for r in self._scope(repo) if r.id not in known)


__all__ = [
    # Re-exported from `wsindex.run`, which is where they live now: every
    # adapter already imports them from here, and a split of this module
    # is not a reason for four other files to change.
    "Authorship",
    "Definition",
    "FileReport",
    "FullPass",
    "IndexReport",
    "Pipeline",
    "Reference",
]


def _within_quota(ranked: list[Hit], *, k: int) -> list[Hit]:
    """Cut a merged list to k, letting history take at most its share.

    Not a filter: commits still answer, and a query whose best answers
    really are commit messages still gets some. What this removes is the
    case where prose outscores code on a question about code and takes
    the whole screen — see `COMMIT_SHARE` for the sweep that fixed the
    number.

    A no-op when the caller already filtered history out, which is why it
    is safe to run on every search.
    """
    allowed = max(1, int(k * COMMIT_SHARE))
    kept: list[Hit] = []
    commits = 0
    for hit in ranked:
        if hit.metadata.get("kind") == Kind.COMMIT.value:
            if commits >= allowed:
                continue
            commits += 1
        kept.append(hit)
        if len(kept) == k:
            break
    return kept
