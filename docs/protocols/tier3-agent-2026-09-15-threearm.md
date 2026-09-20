# Tier 3, with an agent — does it finish the work with less?

_2026-09-15 02:58, thulr `18dc086`, 12 tasks, 88 min._

## Conditions

- One real agent, the same on all three arms, given a real issue and
  the repository **at the commit before the fix**.
- Every arm keeps every ordinary tool; two of them add thulr over
  MCP and take nothing away — a developer with it still has grep.
- `legacy` and `new` differ in **nothing but the wording** the MCP
  server gives the agent. Same index, same code, same evening.
- Graded against the diff the maintainers merged, in the parent's
  line numbers so the two are comparable.
- Tools each arm actually had, as the agent reported at startup: without **6**, legacy **9**, new **9**.

## The gate, declared before the run

`new` lands on the same lines at least as often as `without` and
spends fewer tokens; and it beats `legacy`, which is the same tool
described the old way — otherwise the wording changed nothing and
the difference was the evening.

## Results

|                 |  without |   legacy |      new |
| --------------- | -------: | -------: | -------: |
| same file       | 12 of 12 | 11 of 12 | 12 of 12 |
| **same lines**  |   **11** |   **11** |   **12** |
| edited anything |       12 |       12 |       12 |
| mean tokens     |    54748 |    42304 |    47431 |
| mean turns      |       28 |       18 |       20 |
| mean seconds    |      170 |      115 |      136 |
| total cost      |   $16.01 |    $9.59 |   $10.68 |

**What this does not say.** Whether the fix *works* is not measured:
that needs the project's own tests, and thirty-three repositories
across seven languages do not have a suite this can run. Landing on
the same lines is more than finding the file and less than fixing
the bug, and the gap between those is the agent's judgement, which
is the same on every arm here.

## What the agent actually called

Mean calls per task. The question this answers is whether the
treatment *replaced* any reading or merely added to it — the first
run of this harness found thulr called once a task on top of an
unchanged amount of grep, which costs and saves nothing.

| Tool        | without | legacy |  new |
| ----------- | ------: | -----: | ---: |
| `Bash`      |    18.0 |    9.8 | 11.2 |
| `Read`      |     5.7 |    3.7 |  3.9 |
| `Edit`      |     2.9 |    2.3 |  2.0 |
| `Grep`      |     0.8 |    0.8 |  1.3 |
| `ws:search` |     0.0 |    0.9 |  0.4 |
| `ws:why`    |     0.0 |    0.2 |  0.1 |
| `Write`     |     0.2 |    0.0 |  0.1 |
| `Glob`      |     0.1 |    0.1 |  0.0 |
| `ws:refs`   |     0.0 |    0.0 |  0.2 |

## Raw rows

Transcripts are kept beside the corpus cache, not in this repository.

| Task           | without: file/line | tokens | legacy: file/line | tokens | new: file/line | tokens | issue                                               |
| -------------- | ------------------ | -----: | ----------------- | -----: | -------------- | -----: | --------------------------------------------------- |
| `pow#420`      | yes/yes            |  57938 | yes/yes           |  75666 | yes/yes        |  47504 | Can sign in even though email has not been confirm  |
| `pow#602`      | yes/yes            |   6733 | yes/yes           |   9465 | yes/yes        |  10818 | Switch to :crypto.mac/4 from :crypto.hmac/3         |
| `pow#364`      | yes/yes            |  50287 | yes/yes           |  46616 | yes/yes        |  47948 | nil user_id causes app failure                      |
| `gql.tada#329` | yes/yes            |  41595 | yes/yes           |  37094 | yes/yes        |  43511 | `gql.tada check` returns exit code 0 with errors    |
| `assent#124`   | yes/yes            |  41176 | no/no             |  27527 | yes/yes        |  36204 | Add connection pool to Mint HTTP adapter (turn it   |
| `caddy#7617`   | yes/no             | 241814 | yes/yes           |  98346 | yes/yes        | 104274 | TLS_ALPN challenge doesn't get disabled by Caddyfi  |
| `assent#200`   | yes/yes            |  37092 | yes/yes           |  36977 | yes/yes        |  35940 | “EdDSA” algorithm not working                       |
| `hoofd#95`     | yes/yes            |  42986 | yes/yes           |  47772 | yes/yes        |  54735 | useTitle not updating in React Concurrent Mode      |
| `caddy#6312`   | yes/yes            |  35735 | yes/yes           |  41617 | yes/yes        |  60026 | http/3 support in reverse_proxy module              |
| `caddy#7419`   | yes/yes            |  18904 | yes/yes           |  25566 | yes/yes        |  41356 | Deferred "on close" Log Not Triggered When stream\_ |
| `caddy#7532`   | yes/yes            |  39700 | yes/yes           |  27622 | yes/yes        |  42639 | Caddy 2.11 HTTP 403 error via docker exec caddy re  |
| `xcaddy#93`    | yes/yes            |  43026 | yes/yes           |  33385 | yes/yes        |  44220 | xcaddy doesn't build specified version              |

### Tool use, per task

| Task           | without                        | legacy                                         | new                                      |
| -------------- | ------------------------------ | ---------------------------------------------- | ---------------------------------------- |
| `pow#420`      | Bash:12 Read:9 Edit:3 Glob:1   | Bash:17 Read:6 Edit:1 ws:search:1              | Bash:12 Read:5 Edit:2 ws:search:1        |
| `pow#602`      | Bash:3 Edit:1 Grep:1 Read:1    | Grep:2 Bash:1 Edit:1 Read:1                    | Bash:2 Grep:2 Edit:1 Read:1              |
| `pow#364`      | Bash:13 Read:5 Grep:2 Edit:1   | Bash:15 Read:2 Edit:1 ws:search:1              | Bash:8 Read:6 Edit:1 Grep:1 ws:refs:1    |
| `gql.tada#329` | Bash:14 Read:7 Edit:1          | Bash:10 Read:5 Edit:1 ws:search:1              | Bash:11 Read:7 Edit:1 Grep:1 ws:search:1 |
| `assent#124`   | Bash:12 Edit:7 Read:5 Write:1  | Bash:5 Edit:4 Read:4 ws:search:1 ws:why:1      | Bash:16 Read:2 Write:1                   |
| `caddy#7617`   | Bash:81 Read:26 Edit:3 Write:1 | Bash:26 Read:13 Edit:2 Grep:2 ws:search:1      | Bash:23 Read:10 Grep:3 Edit:2            |
| `assent#200`   | Bash:10 Edit:3 Grep:3 Read:2   | Bash:8 Edit:4 Grep:2 Read:2 ws:search:1        | Bash:8 Edit:3 Grep:2 Read:2              |
| `hoofd#95`     | Bash:20 Edit:6 Read:3          | Bash:12 Edit:4 Read:4 ws:search:1 ws:why:1     | Bash:19 Read:3 Edit:1 ws:refs:1          |
| `caddy#6312`   | Bash:17 Edit:4 Grep:1          | Bash:7 Edit:4 Glob:1 Grep:1 Read:1 ws:search:1 | Bash:12 Edit:7 Grep:2 Read:2 ws:search:1 |
| `caddy#7419`   | Bash:6 Read:4 Grep:2 Edit:1    | Bash:2 Read:2 Edit:1 Grep:1 ws:search:1        | Read:3 Grep:2 Edit:1 ws:search:1         |
| `caddy#7532`   | Bash:17 Read:3 Edit:1          | Bash:8 Read:3 Edit:1 ws:search:1               | Bash:14 Read:4 Grep:3 Edit:1 ws:why:1    |
| `xcaddy#93`    | Bash:11 Edit:4 Read:3 Grep:1   | Bash:7 Edit:4 Grep:1 Read:1 ws:search:1        | Bash:9 Edit:4 Read:2 ws:search:1         |
