"""A reranker that is not on this machine, and why it is the better trade.

A reranker reads a `(query, chunk)` pair together instead of comparing
two vectors, so it sits in the funnel's second stage and sees only the
candidates retrieval already found — a few dozen per search rather than
the whole corpus. That changes what leaving the machine means.

**Turning this on still sends code to somebody else's server.** It sends
the query and `k x 4` candidate chunks per search: forty chunks where a
remote *embedder* would send sixteen thousand, and only the ones a
question already reached. Three orders of magnitude less is not zero, and
this is off by default too.

What it buys, measured on the sixty blind questions of `poe relevance`
with the **local index left exactly as it is** — only the second stage
changes:

| funnel | identifier | descriptive | cross-repo |
| --- | --- | --- | --- |
| local index, no reranker | 8 / 11 of 16 | 2 / 5 of 23 | 1 / 3 of 8 |
| local index + `rerank-2.5` | 13 / 15 | 7 / 12 | 3 / 5 |

Cells are top-three / top-ten. On identifier questions — the class this
tool is positioned around — that is as good as replacing the embedder
wholesale. The gate of 0.50 is cleared at 0.52.

The cost is per search rather than per chunk: about 23 000 tokens a
question here against 3.1 million once for the corpus, so on a
16 000-chunk workspace the two cross at roughly 135 searches. Below that
the reranker is cheaper as well as more private; above it, it is still
more private.
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence

import httpx

from wsindex.rank.reranker import Reranker

RETRIES = 6
"""Attempts before giving up, for the reasons that might pass. A wrong
key fails once — see `wsindex.embed.remote`, which keeps the same rule."""

BATCH_TOKENS = 250_000
"""How much text one rerank request may carry.

Providers cap a batch and answer 400 when it is exceeded, and that 400 is
not retriable: it ends the search rather than slowing it. Voyage allows
600 000 tokens; this is well under, because the estimate below is an
estimate and the failure it prevents is a crash.

Found by running, not by reading a page: a search whose hundred and
twenty candidates happened to be large chunks sent 793 079 tokens and
took the whole query down with it. The number of candidates is bounded
(`RERANK_BUDGET`) and their *size* is not, so a bound on count was never
a bound on bytes."""

BATCH_DOCUMENTS = 500
"""And a cap on count as well, because some providers have one of those
instead. Under either limit, a request carries whichever is smaller."""


def _batches(texts: Sequence[str]) -> list[tuple[int, int]]:
    """Contiguous runs of candidates that fit one request.

    Sized on three characters to the token, which is this project's
    measured estimate elsewhere and errs high here on purpose. A single
    document over the budget still goes on its own: truncating it is the
    provider's business, and dropping it would silently lose a candidate
    the funnel chose.
    """
    runs: list[tuple[int, int]] = []
    start, tokens = 0, 0
    for index, text in enumerate(texts):
        cost = len(text) // 3 + 1
        if index > start and (tokens + cost > BATCH_TOKENS or index - start >= BATCH_DOCUMENTS):
            runs.append((start, index))
            start, tokens = index, 0
        tokens += cost
    runs.append((start, len(texts)))
    return runs


class RemoteReranker(Reranker):
    """Relevance scores from a hosted cross-encoder.

    Attributes:
        model: What the provider calls the model.
        url: The endpoint, in the `{query, documents, model}` shape
            Voyage and Jina both use.
        token_env: **The name of an environment variable**, never a
            token — the same rule the rest of this project keeps.
    """

    def __init__(self, *, model: str, url: str, token_env: str, timeout: float = 120.0) -> None:
        self._model = model
        self._url = url
        self._token_env = token_env
        self._timeout = timeout

    def _token(self) -> str:
        value = os.environ.get(self._token_env)
        if not value:
            raise RuntimeError(f"${self._token_env} is not set, and `[rank] token_env` names it")
        return value

    def _rank(self, query: str, texts: Sequence[str]) -> list[float]:
        """Score every candidate, in as many requests as the limit needs.

        A cross-encoder scores each `(query, document)` pair on its own,
        so splitting the candidates across requests changes no score —
        unlike splitting a list whose order depends on the set. That is
        what makes the batching below safe rather than merely convenient.
        """
        if not texts:
            return []
        scores: list[float] = []
        for start, end in _batches(texts):
            scores.extend(self._post(query, texts[start:end]))
        return scores

    def _post(self, query: str, texts: Sequence[str]) -> list[float]:
        payload = {"query": query, "documents": list(texts), "model": self._model}
        headers = {"Authorization": f"Bearer {self._token()}"}
        for attempt in range(RETRIES):
            try:
                reply = httpx.post(self._url, json=payload, headers=headers, timeout=self._timeout)
                reply.raise_for_status()
            except httpx.HTTPStatusError as exc:
                retriable = exc.response.status_code in (408, 429, 500, 502, 503, 504, 529)
                if not retriable or attempt == RETRIES - 1:
                    raise RuntimeError(
                        f"{self._model} at {self._url} answered "
                        f"{exc.response.status_code}: {exc.response.text[:200]}"
                    ) from exc
                time.sleep(2**attempt)
                continue
            except httpx.TransportError as exc:
                # Caught for the same reason the embedder catches it: a
                # server hanging up mid-request is an accident, not an
                # answer, and it was ending the search instead of being
                # retried like the 503 it resembles.
                if attempt == RETRIES - 1:
                    raise RuntimeError(
                        f"{self._model} at {self._url} could not be reached: {exc}"
                    ) from exc
                time.sleep(2**attempt)
                continue
            # Back into the caller's order, and by index rather than by
            # position: this endpoint answers sorted by score, so trusting
            # arrival order would hand every chunk its neighbour's rank.
            scores = [0.0] * len(texts)
            for row in reply.json()["data"]:
                scores[row["index"]] = float(row["relevance_score"])
            return scores
        raise RuntimeError("unreachable")  # pragma: no cover - the loop returns or raises
