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
Pointed at `qwen2.5:3b` on the same machine, with the shipped local
embedder and everything else unchanged, the same 355 questions went from
138 answers to **131** — the gain of +20 became a loss of 7. The
rewordings show why: asked about disabling a test suite's cleanup, the
small model returns `disable_wiping`, `suite_management`, `set_to_off`,
which are the question's own words spelled as identifiers. The large one
returns "option to skip truncation between tests" — and `truncation` is
the word the code uses and the question does not.

So this stage is not a string operation, it is domain knowledge, and it
is worth exactly as much as the model has. Point `url` at something
small and search gets worse quietly.

**Cutting the question up instead was measured and lost.** Stripping
function words or sliding a window over them gained nothing and lost a
dozen answers of 84: the syntax of a question is signal to a model that
reads language, not noise. What works is a *different wording*, and the
question itself must stay in the fusion — the arm without it scored
worse on every cut.
"""

from wsindex.rewrite.rewriter import FakeRewriter, Rewriter

__all__ = ["FakeRewriter", "Rewriter"]
