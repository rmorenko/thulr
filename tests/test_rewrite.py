"""Asking the question the way the code would phrase it.

The stage itself is three lines of pipeline; what is worth pinning is the
contract around it. A rewriter must never cost an answer — it is optional
by design and its failure has to read as "no rewordings", not as an
error — and the question as typed must always be among the queries,
because the arm that replaced it scored worse on every cut of the
measurement that justified building this.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import httpx
import pytest

from thulr.rewrite import FakeRewriter
from thulr.rewrite.remote import MAX_WORDS, RemoteRewriter, _phrases


def test_a_short_question_yields_nothing_rather_than_noise() -> None:
    assert FakeRewriter().rewrite("port") == []


def test_commentary_and_commands_are_not_queries() -> None:
    """A model told to write phrases writes a shell command now and then.

    Filtered here rather than trusted to the prompt: a prompt is a
    request and this is a contract. The first run of the probe that
    measured this feature got three `grep` invocations back.
    """
    said = "\n".join(
        [
            "Here are some options:",
            "grep -rn 'retry' --include=*.go .",
            "retry backoff configuration for outbound calls",
            "  - session heartbeat ping interval  ",
            "```",
            " ".join(["word"] * (MAX_WORDS + 2)),
        ]
    )

    assert _phrases(said, 5) == [
        "retry backoff configuration for outbound calls",
        "session heartbeat ping interval",
    ]


def test_a_compound_term_is_a_query_even_though_it_is_one_word() -> None:
    """The first filter here used a three-word minimum and a second model
    showed it up: `qwen2.5:3b` answers in compounds, which are exactly
    what a search wants. A threshold on length encodes one model's prose
    style; what was meant is that a query is not a sentence."""
    said = "heartbeat-frequency\nheartbeat_check_interval\nSure, here you go."

    assert _phrases(said, 5) == ["heartbeat-frequency", "heartbeat_check_interval"]


def test_a_rewriter_that_cannot_reach_its_model_costs_no_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every other remote call here fails loudly; this one must not.

    A search that would have worked cannot be turned into an error by an
    optional stage meant to improve it.
    """

    def dead(url: str, **kwargs: object) -> object:
        raise httpx.ConnectError("nothing is listening")

    monkeypatch.setattr("thulr.rewrite.remote.httpx.post", dead)
    monkeypatch.setattr("thulr.rewrite.remote.time.sleep", lambda _: None)

    assert RemoteRewriter(model="m", url="http://nowhere").rewrite("where is retry") == []


def test_a_missing_key_is_not_an_exception_either(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REWRITE_KEY", raising=False)
    ranker = RemoteRewriter(model="m", url="http://x", token_env="REWRITE_KEY")

    assert ranker.rewrite("where is retry") == []


def test_a_local_server_needs_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole privacy argument for this stage: point it at localhost
    and the promise that nothing leaves the machine survives."""
    seen: dict[str, object] = {}

    def fake_post(url: str, **kwargs: object) -> object:
        seen.update(kwargs)
        seen["url"] = url

        class Reply:
            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def json() -> dict[str, object]:
                return {"choices": [{"message": {"content": "retry backoff settings here"}}]}

        return Reply()

    monkeypatch.setattr("thulr.rewrite.remote.httpx.post", fake_post)
    rewriter = RemoteRewriter(model="m", url="http://localhost:11434/v1/chat/completions")

    assert rewriter.rewrite("where is retry") == ["retry backoff settings here"]
    assert seen["headers"] == {}


def test_the_question_is_always_asked_and_the_lists_are_fused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The two halves of the contract, in one search.

    Measured before this was built: the arm that searched only the
    rewordings scored worse than the one that kept the question, on every
    cut and both corpora. So the question is not one option among
    several — it is always asked, and always first.
    """
    from thulr.config import Config, Provider, Repository
    from thulr.embed import FakeEmbedder
    from thulr.pipeline import Pipeline
    from thulr.store import LanceDBStore

    for name in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"):
        monkeypatch.setenv(name, "/dev/null")
    for name, value in (("NAME", "Test"), ("EMAIL", "test@example.invalid")):
        monkeypatch.setenv(f"GIT_AUTHOR_{name}", value)
        monkeypatch.setenv(f"GIT_COMMITTER_{name}", value)
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text("def alpha():\n    return 'alpha'\n")
    (repo / "src" / "b.py").write_text("def beta():\n    return 'beta'\n")
    for args in (["init", "-q", "--initial-branch=main"], ["add", "-A"], ["commit", "-qm", "one"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    Config.reset()
    config = Config.default("rewriting", provider=Provider.FAKE)
    config.add_repo(Repository(id="repo", path=str(repo)))
    store = LanceDBStore(uri=str(tmp_path / "index"), embedder=FakeEmbedder())

    asked: list[str] = []

    class Recording(FakeRewriter):
        def rewrite(self, question: str) -> list[str]:
            asked.append(question)
            return ["alpha definition", "beta definition"]

    plain = Pipeline(store=store, config=config, state_dir=tmp_path / "state")
    plain.index()
    before = plain.search("what does alpha return", k=5)

    widened = Pipeline(
        store=store, config=config, state_dir=tmp_path / "state", rewriter=Recording()
    )
    after = widened.search("what does alpha return", k=5)

    assert asked == ["what does alpha return"], "the rewriter sees the question as typed"
    assert before, "the single-query search still answers"
    assert {(h.repo, h.path) for h in before} <= {(h.repo, h.path) for h in after}, (
        "fusing more queries cannot drop what one query already found"
    )
