"""What a rewriter is, and one that needs nothing to run."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Rewriter(ABC):
    """Other ways of asking the same question.

    The contract is deliberately narrow: given a question, return zero or
    more rewordings. Returning nothing is a valid answer and means the
    search proceeds exactly as it does today — a rewriter that fails must
    cost the caller an opportunity, never an answer.
    """

    @abstractmethod
    def rewrite(self, question: str) -> list[str]:
        """Rewordings of `question`, best first, possibly empty."""


class FakeRewriter(Rewriter):
    """Deterministic rewordings for tests, and a shape to assert against.

    Not a useful rewriter and not meant to be: it exists so the wiring
    can be tested without a model, the way `FakeEmbedder` does.
    """

    def __init__(self, *, count: int = 2) -> None:
        """How many rewordings this fake produces."""
        self._count = count

    def rewrite(self, question: str) -> list[str]:
        """Tails of the question, which is enough shape to assert against."""
        words = question.split()
        if len(words) < 2:
            return []
        return [" ".join(words[i:]) for i in range(1, self._count + 1) if words[i:]]
