# Tier 3, with an agent — does it finish the work with less?

_2026-09-15 01:11, thulr `18dc086`, 12 tasks, 69 min._

## Conditions

- One real agent, the same on both sides, given a real issue and the
  repository **at the commit before the fix**.
- Both keep every ordinary tool; the treatment adds thulr over MCP
  and takes nothing away — a developer with it still has grep.
- Graded against the diff the maintainers merged, in the parent's
  line numbers so the two are comparable.
- Tools the runs actually had, as the agent reported at startup: **9** with thulr, **6** without — `Bash`, `Edit`, `Glob`, `Grep`, `Read`, `Write`, `mcp__thulr__refs`, `mcp__thulr__search`, `mcp__thulr__why`.

## The gate, declared before the run

With thulr the agent lands on the same lines at least as often,
and spends fewer tokens doing it.

## Results

|                 | with thulr |  without |
| --------------- | ---------: | -------: |
| same file       |   11 of 12 | 11 of 12 |
| **same lines**  |     **11** |    **9** |
| edited anything |         12 |       12 |
| mean tokens     |      47525 |    51415 |
| mean turns      |         18 |       25 |
| mean seconds    |        149 |      186 |
| total cost      |     $10.34 |   $13.27 |

**What this does not say.** Whether the fix *works* is not measured:
that needs the project's own tests, and thirty-three repositories
across seven languages do not have a suite this can run. Landing on
the same lines is more than finding the file and less than fixing
the bug, and the gap between those is the agent's judgement, which
is the same on both sides here.

## What the agent actually called

Mean calls per task. The question this row answers is whether the
treatment *replaced* any reading or merely added to it.

| Tool        | with thulr | without |
| ----------- | ---------: | ------: |
| `Bash`      |       10.8 |    16.0 |
| `Read`      |        1.8 |     3.1 |
| `Edit`      |        2.1 |     2.2 |
| `Grep`      |        1.0 |     2.2 |
| `ws:search` |        0.8 |     0.0 |
| `Write`     |        0.2 |     0.6 |
| `ws:why`    |        0.3 |     0.0 |
| `ws:refs`   |        0.3 |     0.0 |
| `Glob`      |        0.0 |     0.1 |

## Raw rows

Transcripts are kept beside the corpus cache, not in this repository.

| Task            | with: file/line | tokens | without: file/line | tokens | issue                                                         |
| --------------- | --------------- | -----: | ------------------ | -----: | ------------------------------------------------------------- |
| `gql.tada#409`  | yes/yes         |  65388 | no/no              |  57310 | gql.tada turbo does not regenerate cache file when a scalar   |
| `gql.tada#286`  | yes/yes         |  34349 | yes/yes            |  37959 | `generate output` doesn't seem to work by default in CI       |
| `pow#292`       | yes/yes         |  52495 | yes/yes            |  51093 | Keeping scope in generated routes                             |
| `pow#290`       | no/no           | 105195 | yes/yes            |  33287 | Limit login attempts                                          |
| `caddy#7743`    | yes/yes         |  86295 | yes/no             | 163461 | Breaking change in 2.11.3?                                    |
| `GraphQLSP#333` | yes/yes         |  43945 | yes/yes            |  42066 | Schema name is not computed when using multiple schemas       |
| `caddy#7727`    | yes/yes         |  24756 | yes/yes            |  40337 | Client TLS not working on v2.11.3                             |
| `caddy#7599`    | yes/yes         |  13988 | yes/yes            |  11018 | Unexpected behaviour when renaming the query field - field g  |
| `caddy#7534`    | yes/yes         |  32131 | yes/yes            |  35918 | tls_client_subject set to literal \`{http.request.tls.client. |
| `caddy#7433`    | yes/yes         |  58168 | yes/no             |  58034 | caddy fmt does not format multi-line strings properly         |
| `pow#602`       | yes/yes         |   9748 | yes/yes            |   7094 | Switch to :crypto.mac/4 from :crypto.hmac/3                   |
| `gql.tada#32`   | yes/yes         |  43843 | yes/yes            |  79403 | RFC: allow reacting to client-side directives                 |

### Tool use, per task

| Task            | with thulr                                          | without                              |
| --------------- | --------------------------------------------------- | ------------------------------------ |
| `gql.tada#409`  | Bash:20 Edit:3 Grep:2 Write:1 ws:refs:1 ws:search:1 | Bash:19 Grep:4 Read:4 Edit:1 Write:1 |
| `gql.tada#286`  | Bash:9 Read:4 Edit:3 Grep:1 ws:search:1 ws:why:1    | Bash:10 Read:7 Edit:3 Grep:2         |
| `pow#292`       | Bash:18 Edit:3 Read:2 ws:search:1                   | Bash:18 Read:4 Edit:3                |
| `pow#290`       | Bash:19 Read:3 ws:search:2 Edit:1 Grep:1 ws:refs:1  | Bash:16 Edit:1 Write:1               |
| `caddy#7743`    | Bash:26 Edit:2 Read:1 ws:why:1                      | Bash:54 Grep:5 Edit:1 Read:1         |
| `GraphQLSP#333` | Bash:11 Read:4 Edit:2 ws:refs:1 ws:search:1         | Bash:14 Grep:4 Edit:2 Read:2         |
| `caddy#7727`    | Bash:4 Edit:1 ws:search:1                           | Bash:11 Read:3 Grep:2 Edit:1         |
| `caddy#7599`    | Bash:1 Edit:1 Read:1 ws:search:1 ws:why:1           | Bash:3 Edit:1 Grep:1 Read:1          |
| `caddy#7534`    | Grep:5 Bash:3 Read:2 Edit:1 ws:refs:1 ws:why:1      | Grep:5 Read:5 Edit:4 Bash:3          |
| `caddy#7433`    | Bash:4 Edit:3 Read:1 ws:search:1                    | Bash:15 Read:5 Edit:4 Write:2 Glob:1 |
| `pow#602`       | Bash:4 Edit:2 Grep:1 Read:1                         | Bash:1 Edit:1 Grep:1 Read:1          |
| `gql.tada#32`   | Bash:10 Edit:3 Read:3 Grep:2 Write:1 ws:search:1    | Bash:28 Edit:4 Read:4 Write:3 Grep:2 |
