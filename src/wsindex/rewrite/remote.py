"""A rewriter that asks a language model, wherever that model lives.

The wire shape is the chat-completions one — `{model, messages}` in,
`choices[0].message.content` out — because it is what every local runner
speaks as well as every hosted provider. That choice is the privacy
argument: point `url` at `http://localhost:11434/v1/chat/completions` and
the promise that nothing leaves the machine survives a feature that
would otherwise end it.
"""

from __future__ import annotations

import os
import time

import httpx

from wsindex.rewrite.rewriter import Rewriter

RETRIES = 4
"""Fewer than the embedder's six, because this stage is optional.

A failed embedding is an unindexed chunk and a failed rerank is a worse
order; a failed rewording is the search a user would have got anyway. So
it gives up sooner and never raises — see `rewrite`."""

MAX_WORDS = 14
"""Longest a reworded query may be before it is dropped.

Models answer this prompt with a shell command about once in thirty, and
a paragraph of explanation about as often. Both are long; real queries
are not. Measured on 439 rewordings: nothing useful exceeded twelve
words."""

PROMPT = """A developer asked this about a codebase you cannot see:

    {question}

Rewrite it as {count} short phrases for a semantic search engine — the
kind you would type into a search box, not a shell. Each phrase should
describe the same thing in the vocabulary the code itself is likely to
use: the words a programmer would have chosen for the functions,
settings and types involved.

Plain phrases of three to ten words. No shell commands, no grep, no
regular expressions, no quotes, no numbering, no explanation, no file
names. One phrase per line and nothing else."""


class RemoteRewriter(Rewriter):
    """Rewordings from a chat model over HTTP.

    Attributes:
        model: What the provider calls the model.
        url: A chat-completions endpoint, hosted or on this machine.
        token_env: **The name of an environment variable**, never a
            token — the same rule the rest of this project keeps. May be
            empty for a local server that wants no authorisation.
        count: How many rewordings to ask for.
    """

    def __init__(
        self,
        *,
        model: str,
        url: str,
        token_env: str = "",
        count: int = 3,
        timeout: float = 30.0,
    ) -> None:
        self._model = model
        self._url = url
        self._token_env = token_env
        self._count = count
        self._timeout = timeout

    def rewrite(self, question: str) -> list[str]:
        """Other wordings, or nothing at all when the model cannot be had.

        **Never raises.** Every other remote call in this project fails
        loudly, and this one must not: a search that would have worked
        cannot be turned into an error by an optional stage that was
        meant to improve it. A caller gets fewer queries, which is the
        behaviour of the version before this existed.
        """
        try:
            said = self._ask(question)
        except (httpx.HTTPError, KeyError, ValueError, RuntimeError):
            return []
        return _phrases(said, self._count)

    def _ask(self, question: str) -> str:
        headers = {}
        if self._token_env:
            token = os.environ.get(self._token_env)
            if not token:
                raise RuntimeError(f"${self._token_env} is not set")
            headers["Authorization"] = f"Bearer {token}"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "user", "content": PROMPT.format(question=question, count=self._count)}
            ],
            # Zero, because a search that answers differently on a second
            # run is not a search this project ships: determinism is a
            # promise `for-agents.md` makes in so many words.
            "temperature": 0,
            "max_tokens": 200,
        }
        for attempt in range(RETRIES):
            try:
                reply = httpx.post(self._url, json=payload, headers=headers, timeout=self._timeout)
                reply.raise_for_status()
            except (httpx.HTTPStatusError, httpx.TransportError):
                if attempt == RETRIES - 1:
                    raise
                time.sleep(2**attempt)
                continue
            body = reply.json()
            return str(body["choices"][0]["message"]["content"])
        raise RuntimeError("unreachable")  # pragma: no cover - the loop returns or raises


def _phrases(said: str, count: int) -> list[str]:
    """The lines of an answer that are queries rather than commentary.

    A model told to write phrases writes a shell command now and then,
    and a sentence of preamble rather more often. Filtering here rather
    than trusting the prompt: the prompt is a request and this is a
    contract.
    """
    out: list[str] = []
    for raw in said.splitlines():
        line = raw.strip(' -*\t".')
        if not 3 <= len(line.split()) <= MAX_WORDS:
            continue
        if line.startswith(("grep", "rg ", "find ", "$", "#", "```")):
            continue
        # "Here are some options:" is the shape of a preamble and the
        # shape of nothing else — a query does not end in a colon.
        if line.endswith(":"):
            continue
        out.append(line)
    return out[:count]
