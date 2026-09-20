# wsindex for whoever decides whether the code may leave

## The short answer

By default, nothing leaves. Not telemetry, not source, not queries. The
embedding model runs in the process that indexes, the index is a file
beside the config, and a warm search opens **zero sockets** — measured,
not asserted.

Three things can change that, and none of them is a default. Each has to
be typed into a config file, and each is named below with exactly what it
sends.

**And the part a security reviewer is usually not told.** Staying at the
default costs quality, and the amount is measured. On 204 questions
harvested from the indexed projects' own issue trackers, the fully local
default finds the right file in the top ten 98 times; `ripgrep` finds it
71\. Turning on a hosted *reranker* — which sends the query and about
forty candidate chunks per search, never the corpus — takes it to 109.
Replacing the embedder as well, which does send every chunk once, takes
it to 132.

So the decision in front of you is not "secure or insecure". It is which
posture to buy, and most of them are defensible:

| Posture                 | Finds it (of 204) | What leaves        |
| ----------------------- | ----------------: | ------------------ |
| The default, hybrid on  |                98 | Nothing            |
| Hybrid turned off       |                72 | Nothing            |
| Hosted reranker         |               109 | Query + ~40 chunks |
| Hosted embedder as well |               132 | Every chunk, once  |

A fifth posture arrived later and is not in that column because it was
measured on a different corpus; putting a rescaled number in a table of
measured ones is how a table stops being evidence. On the 355 harvested
questions, the **hosted rewriter** takes the fully local configuration
from 138 answers to **158** (p = 0.0055), and the hosted embedder with
its rewordings reaches 217 against 192.

The first row is the default, sends nothing, and is already ahead of the
control — 98 against ripgrep's 71, p = 0.0016. Fusing a lexical pass
with the vector one is what holds the top of it: the second row is the
same tool with that switched off, and it puts the right file *first* for
1 question of 204 instead of 36. The reranker row is the one most
organisations used to argue about; it buys 11 answers for a query and
forty chunks per search.

**The rewriter is the cheapest of the three by a wide margin.** It sends
the question the user typed and no code at all — not a chunk, not a path,
not a name. And the wire shape is the chat-completions one, so
`[rewrite] url` may point at a model on the user's own machine, in which
case it sends nothing anywhere.

A caution that belongs here rather than in a footnote: the question a
developer types is not always innocent. "Why does our Acme Bank
reconciliation job drop rows" names a client. A rewriter sends that
sentence to whoever `url` points at, and nothing else — which is far less
than the rows below it, and not zero.

## What opens a socket, and when

| When                                     | What goes out                                        | Avoidable                |
| ---------------------------------------- | ---------------------------------------------------- | ------------------------ |
| First index on a machine                 | The model is downloaded from the model host (~90 MB) | Yes — pre-seed the cache |
| Every index and search after             | Nothing                                              | —                        |
| `wsindex sync` on a repo with a `remote` | Whatever `git fetch` sends                           | Only by not using it     |
| `[embeddings] provider = "remote"`       | **Every chunk of every repo**                        | Yes — it is off          |
| `[rank] provider = "remote"`             | The query and ~40 candidate chunks per search        | Yes — it is off          |
| `[rewrite] enabled = true`               | **The question, and no code** — once per search      | Yes — it is off          |
| `wsindex serve`                          | Binds a socket you asked it to bind                  | Yes                      |

The model download is once and offline afterwards: loading tries the
local cache before the network on every subsequent run.

## The three remote options are not the same decision

A **remote rewriter** sends one sentence per search: the question, as
typed. No chunk, no path, no identifier. It is the only one of the three
that can be pointed at `localhost` and keep the whole promise, because it
speaks the chat-completions shape every local runner speaks.

A **remote embedder** sends your whole corpus, once per index and again
on every re-index. Sixteen thousand chunks for a small workspace.

A **remote reranker** sends the query and the candidates one search
already found — about forty chunks, and only the ones related to what was
asked. Three orders of magnitude less, and the index never leaves.

If somebody asks for the quality of a hosted model, grant the rewriter
first and the reranker second. The rewriter is the largest measured gain
per byte sent by a wide margin, and the reranker reaches the same 13 of
16 on identifier questions as replacing the embedder outright.

One thing the rewriter is **not**: a way to get hosted quality from a
local model. Measured, `qwen2.5:3b` rewording on the same machine takes
the local configuration from 138 answers to 131 — worse than leaving it
off — and `qwen2.5:7b` reaches 140, which is break-even. The gain is the
model's knowledge of what code is called, and a small model does not have
it.

All three name their key as `token_env` — **the name of an environment
variable, never the key itself**. A token in a config file is a token in
a git history. An unset variable is reported by name rather than as a
401\.

## `trust_remote_code` is off, and that is a security decision

Several embedding and reranking models ship their own Python and expect
it to be executed at load. That is arbitrary code from a model host
running in the process that reads your source. It is off by default and
has to be turned on explicitly per workspace.

An operational note that supports the same decision: of five models tried
that require it, **five failed to load** — broken by a library upgrade,
missing packages, or allocating tens of gigabytes. The models that shipped
no code of their own all worked.

## The server, if a team shares one

- **Authentication is a bearer token**, named by the config as an
  environment variable. Binding to a public address without one requires
  `--insecure`, spelled that way on purpose.
- **The token belongs to the server, not to a person.** There is no
  per-user identity, and that is deliberate: inventing one would mean
  per-user authentication *and* a log of individual people's questions
  attributed to them. The search log records no identity and the admin
  page reports aggregates only.
- **Consequence to state plainly:** whoever holds the token can search
  everything the server has indexed. If a workspace mixes repositories
  with different audiences, run separate servers rather than relying on
  scoping that does not exist.
- Endpoints are `/search`, `/index`, `/status`, `/healthz`, `/metrics`.
  The metrics carry no query text — route labels only.

## What is on disk

The index lives beside the config (or where `[store] uri` says). It
contains the text of every indexed chunk, its path and line range, and
its vector — so **the index is as sensitive as the source it was built
from**. Treat it that way when choosing where it lives and who can read
it, especially with `uri` pointing at shared storage.

`wsindex stats` keeps a local log of the queries this machine asked. It
is local by construction and never written to the link store, because
that store may be a shared Postgres and one person's questions do not
belong in a team's database.

## How to check any of this yourself

```console
$ wsindex status                     # what is configured, and where the index is
$ grep -n 'provider\|token_env\|url' wsindex.toml   # anything remote is visible here
```

Nothing above is a claim you have to take on trust, but be precise about
what each piece of evidence covers. `test_searching_opens_no_sockets`
runs the search path — including the write that records it — and fails if
anything connects; **its own docstring says what it does not prove**,
because it uses the fake embedder and so says nothing about the real
model. That was measured separately by watching a warm search with the
real model open zero sockets. The two together are the claim; neither is
on its own.

The config is the only place a remote endpoint can be named, which means
`grep` over `wsindex.toml` is a complete audit of where this tool may
talk. That part needs no trust at all.
