"""The relevance harness's judgement, which is the part a test can reach.

Not the sixty questions — those need a pinned corpus, a real model and
five minutes, and what they measure is the product rather than this file.
What is tested here is what the harness *decides*: when fewer answers
counts as a regression, and when two runs are not comparable at all.

A guard nobody has watched fail is not a guard, and this one exists
precisely so that a future change to search cannot quietly undo step 3.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from relevance import Graded, Workspace, compare, counted, vector_key

BASELINE = {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "full": False,
    "found": {"literal": 9, "literal@3": 5, "descriptive": 4, "cross-repo": 4},
}


def graded(klass: str, rank: int | None, *, reachable: bool = True) -> Graded:
    return Graded(
        id="q1",
        klass=klass,
        text="?",
        truth="repo/path.py",
        reachable=reachable,
        rank=rank,
        deep_rank=rank,
        control="missed",
        control_files=0,
        commits_in_top3=0,
    )


def test_counting_splits_the_top_ten_from_the_top_three() -> None:
    # Both are kept because they move independently: the commit quota of
    # step 3 lifted identifier answers into the top three without
    # changing how many were in the top ten at all.
    space = Workspace(org="w", graded=[graded("literal", 1), graded("literal", 7)])

    found = counted([space])

    assert found["literal"] == 2
    assert found["literal@3"] == 1


def test_a_missed_question_counts_for_nothing() -> None:
    space = Workspace(org="w", graded=[graded("descriptive", None)])

    assert counted([space])["descriptive"] == 0


def test_no_drop_is_no_complaint() -> None:
    same = {"literal": 9, "literal@3": 5, "descriptive": 4, "cross-repo": 4}

    assert compare(same, BASELINE) == []


def test_more_answers_than_before_is_not_a_regression() -> None:
    # The interesting direction is one-sided. A change that finds more is
    # the point of the exercise, and a guard that complained about it
    # would be turned off within a week.
    better = {"literal": 13, "literal@3": 7, "descriptive": 4, "cross-repo": 4}

    assert compare(better, BASELINE) == []


def test_one_answer_fewer_is_a_regression() -> None:
    # No tolerance band, unlike the benchmark harness: that measures
    # time, which is noisy, and this measures which file came back, on a
    # corpus pinned to a sha with a fixed model.
    worse = {"literal": 9, "literal@3": 5, "descriptive": 3, "cross-repo": 4}

    reported = compare(worse, BASELINE)

    assert len(reported) == 1
    assert "descriptive" in reported[0]
    assert "4 -> 3" in reported[0]


def test_a_class_that_vanished_is_reported_rather_than_skipped() -> None:
    # The failure that hides: a renamed class silently answers zero
    # questions and a naive comparison finds nothing to compare.
    reported = compare({"literal": 9, "literal@3": 5}, BASELINE)

    assert any("descriptive" in line for line in reported)
    assert any("cross-repo" in line for line in reported)


def test_a_baseline_from_another_model_is_not_a_baseline() -> None:
    # Step 4 graded eight models against these same questions. Numbers
    # from CodeRankEmbed are a different question, not a worse answer,
    # and comparing them silently would turn a trade into a bug report.
    saved = {**BASELINE, "model": "nomic-ai/CodeRankEmbed"}

    reported = compare({"literal": 13, "literal@3": 7, "descriptive": 2, "cross-repo": 3}, saved)

    assert "another model" in reported[0]


def test_an_unreachable_question_still_counts_as_not_found() -> None:
    # A file thulr never indexed cannot be retrieved, and the baseline
    # must keep seeing that as zero — otherwise a coverage regression
    # would hide behind "well, it was unreachable anyway". Reachability
    # is reported beside the score, not subtracted from it.
    space = Workspace(org="w", graded=[graded("descriptive", None, reachable=False)])

    assert counted([space])["descriptive"] == 0


def _key(monkeypatch: pytest.MonkeyPatch) -> str:
    from thulr.config import Config

    Config.reset()
    return vector_key("org", [{"id": "r", "sha": "abc"}], Config.default("keytest"))


def test_the_index_key_notices_a_change_to_chunking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The cache's whole safety argument, in one assertion.

    Keeping an index between runs is only defensible while the key sees
    everything that decides what a stored vector is. It fails silently
    when it does not: the numbers still come out, they are just about the
    previous chunker.
    """
    import thulr.ingest.chunker as chunker

    before = _key(monkeypatch)
    source = Path(chunker.__file__)
    original = source.read_bytes()
    try:
        source.write_bytes(original + b"\n# changed\n")
        assert _key(monkeypatch) != before
    finally:
        source.write_bytes(original)
    assert _key(monkeypatch) == before


def test_the_index_key_ignores_a_change_to_ranking(monkeypatch: pytest.MonkeyPatch) -> None:
    """And the other half, which is why the cache is worth having.

    Ranking is the thing this instrument is used to measure. If touching
    `pipeline.py` re-embedded the corpus, a hosted run would cost fifty
    minutes and real money per idea, and the ideas would go unmeasured.
    """
    import thulr.pipeline as pipeline

    before = _key(monkeypatch)
    source = Path(pipeline.__file__)
    original = source.read_bytes()
    try:
        source.write_bytes(original + b"\n# changed\n")
        assert _key(monkeypatch) == before
    finally:
        source.write_bytes(original)


def test_a_probe_can_declare_what_the_source_cannot_show(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`probes/ast_vs_text.py` takes the parser away at runtime, so no
    file changes and nothing above would notice. The tag is how such a
    probe keeps its two arms from sharing one index."""
    before = _key(monkeypatch)
    monkeypatch.setenv("THULR_INDEX_TAG", "windows")
    assert _key(monkeypatch) != before
