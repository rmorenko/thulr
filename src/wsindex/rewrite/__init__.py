"""Rewording a question before it is searched.

A person types one query and does not know what the code calls itself.
An agent, measured in this repository, types three or four and reaches
the answer far more often — not because it searches better but because
it *asks differently*. This stage gives the person that.

Measured before it was built, on two corpora and both embedders, fusing
the rewordings with the question as typed:

| configuration            | corpus            | as typed | + rewordings |     p |
| ------------------------ | ----------------- | -------: | -----------: | ----: |
| `voyage-code-4` + rerank | 355 harvested     |      192 |      **217** | .0002 |
| the shipped local model  | 355 harvested     |      138 |      **158** | .0055 |
| `voyage-code-4` + rerank | 84 authored       |       61 |       **68** | .0391 |
| the same, descriptive    | 42                |       21 |       **28** | .0156 |

**What it sends is the question and nothing else.** No code leaves the
machine — which makes this the smallest concession in the project: the
hosted reranker sends forty chunks per search, a hosted embedder sends
the corpus once. Point `url` at a local server and it sends nothing at
all, which is why the wire shape below is the one every local runner
speaks.

**Cutting the question up instead was measured and lost.** Stripping
function words or sliding a window over them gained nothing and lost a
dozen answers of 84: the syntax of a question is signal to a model that
reads language, not noise. What works is a *different wording*, and the
question itself must stay in the fusion — the arm without it scored
worse on every cut.
"""

from wsindex.rewrite.rewriter import FakeRewriter, Rewriter

__all__ = ["FakeRewriter", "Rewriter"]
