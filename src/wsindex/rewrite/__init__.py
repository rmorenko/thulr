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

**The model has to know what code is called, and a small one does not.**
The same 355 questions, the shipped local embedder, everything unchanged
but who writes the rewordings:

| rewritten by       | answers | against as typed |      p |
| ------------------ | ------: | ---------------: | -----: |
| nobody — as typed  |     138 |                — |      — |
| `qwen2.5:3b` local |     131 |               -7 |   0.34 |
| `qwen2.5:7b` local |     140 |               +2 |   0.88 |
| a frontier model   | **158** |          **+20** | 0.0055 |

A dose-response, not noise. The rewordings say why: asked how to disable
a test suite's cleanup, the small model returns `disable_wiping`,
`set_to_off` — the question's own words spelled as identifiers — and the
large one returns "option to skip truncation between tests", where
`truncation` is a word the code uses and the question does not.

So this stage is not a string operation, it is knowing what code is
called, and it is worth what the model knows. There is no fully local
configuration that wins: three billion parameters is worse than not
rewording at all, and seven is break-even for 4.7 GB of weights and
seconds a query. Point `url` at something small and search gets worse
quietly.

**Depth is a substitute for this, and that has to be said.** The
measurements above fix `k=10`. Asked again at `k=30`, the same corpus
answers 267 as typed and 272 rewritten — five more, and not significant.
Raising `k` alone is worth +75 where rewriting is worth +25, costs no
model call, and adds no latency.

What rewriting buys is answers *per chunk read*: 217 in ten hits against
267 in thirty. So the two are alternatives rather than a stack — worth
turning on for a reader who wants a short list, and worth leaving off by
a caller that already asks for depth. The MCP surface defaults to
`k=20` for exactly that reason and should be assumed to need this less.

**Cutting the question up instead was measured and lost.** Stripping
function words or sliding a window over them gained nothing and lost a
dozen answers of 84: the syntax of a question is signal to a model that
reads language, not noise. What works is a *different wording*, and the
question itself must stay in the fusion — the arm without it scored
worse on every cut.
"""

from wsindex.rewrite.rewriter import FakeRewriter, Rewriter

__all__ = ["FakeRewriter", "Rewriter"]
