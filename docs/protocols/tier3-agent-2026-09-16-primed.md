# Tier 3, with an agent — does it finish the work with less?

_2026-09-16 03:46, thulr `0732e54`, 24 tasks, 285 min._

## Conditions

- One real agent, the same on all three arms, given a real issue and
  the repository **at the commit before the fix**.
- Every arm keeps every ordinary tool; two of them add thulr over
  MCP and take nothing away — a developer with it still has grep.
- `local` and `primed` read **the same index**, so what differs
  between them is delivery: one is a server the agent may call, the
  other is five ranked locations handed over in the task itself.
- Graded against the diff the maintainers merged, in the parent's
  line numbers so the two are comparable.
- **The whole organisation is checked out and indexed**, not just the repository the issue names; siblings sit where they stood that day, so nothing in the workspace describes the fix.
- Tools each arm actually had, as the agent reported at startup: without **6**, local **9**, primed **6**.

## The gate, declared before the run

`primed` lands on the same lines more often than `without`,
counted in **paired** tasks rather than a mean, because one control
that thrashes carries a mean on its own. That is the whole question
this arm exists for: if handing the answer over changes nothing,
the information was never what the agent was short of, and no
amount of making it easier to ask for will help.

## Results

|                 |  without |    local |   primed |
| --------------- | -------: | -------: | -------: |
| same file       | 22 of 24 | 22 of 24 | 21 of 24 |
| **same lines**  |   **19** |   **19** |   **18** |
| edited anything |       24 |       24 |       24 |
| mean tokens     |    50022 |    75794 |    77278 |
| mean turns      |       24 |       31 |       35 |
| mean seconds    |      168 |      248 |      253 |
| total cost      |   $24.18 |   $42.42 |   $45.77 |

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

| Tool        | without | local | primed |
| ----------- | ------: | ----: | -----: |
| `Bash`      |    14.6 |  17.9 |   21.5 |
| `Read`      |     4.6 |   6.2 |    7.6 |
| `Edit`      |     2.4 |   2.5 |    2.9 |
| `Grep`      |     2.1 |   1.4 |    2.3 |
| `ws:search` |     0.0 |   1.7 |    0.0 |
| `Write`     |     0.1 |   0.1 |    0.3 |
| `ws:why`    |     0.0 |   0.3 |    0.0 |
| `ws:refs`   |     0.0 |   0.1 |    0.0 |
| `Glob`      |     0.0 |   0.0 |    0.0 |

## Raw rows

Transcripts are kept beside the corpus cache, not in this repository.

| Task             | without: file/line | tokens | local: file/line | tokens | primed: file/line | tokens | issue                                              |
| ---------------- | ------------------ | -----: | ---------------- | -----: | ----------------- | -----: | -------------------------------------------------- |
| `GraphQLSP#126`  | yes/yes            |  37396 | yes/yes          |  61493 | yes/yes           |  45872 | GraphQL field descriptions in IntelliSense have br |
| `caddy#7532`     | yes/yes            | 115775 | yes/yes          | 155663 | yes/yes           |  69283 | Caddy 2.11 HTTP 403 error via docker exec caddy re |
| `caddy#7782`     | yes/no             |  24020 | yes/no           |  22403 | yes/no            |  14952 | http.request.proto is wonky for HTTP/2 and HTTP/3  |
| `caddy#7894`     | yes/no             |  21511 | yes/yes          |  51113 | yes/yes           |  53287 | skip_install_trust ignored by internal issuers whe |
| `pow_assent#104` | yes/yes            |  37871 | yes/yes          |  58808 | yes/yes           |  33006 | Installation error as dependency resolution failed |
| `pow#473`        | yes/yes            |  45678 | yes/yes          |  79195 | yes/yes           |  75196 | Unexpected warnings during tests                   |
| `caddy#6312`     | yes/yes            |  37590 | yes/yes          |  74975 | yes/yes           |  46748 | http/3 support in reverse_proxy module             |
| `pow#119`        | yes/yes            |  50763 | yes/yes          |  56973 | no/no             | 104516 | POW custom routes don't seem to work?              |
| `pow_assent#129` | no/no              |  80435 | no/no            | 146295 | no/no             | 312202 | Switching OAuth provider when the user_id field is |
| `gql.tada#368`   | yes/yes            | 142905 | yes/yes          | 141433 | yes/yes           | 129246 | Incorrect fragment type using interfaces           |
| `xcaddy#281`     | yes/no             |  20542 | yes/no           |  39467 | yes/no            |  28624 | Error: unknown flag: --config on `xcaddy run`      |
| `pow_assent#143` | yes/yes            |  50317 | yes/yes          |  86333 | yes/yes           |  89468 | PowAssent for Phoenix API and SPA / mobile app     |
| `pow#709`        | no/no              |  55142 | yes/yes          |  43509 | no/no             |  48632 | Upgrading POW from 1.6 to 1.7                      |
| `caddy#7898`     | yes/yes            |  49676 | yes/yes          |  50813 | yes/yes           |  46378 | Nested named route invocation undetected           |
| `pow#71`         | yes/yes            |  27816 | yes/yes          |  25144 | yes/yes           |  29923 | Disable registration routes                        |
| `caddy#7017`     | yes/yes            |  43464 | yes/no           |  50893 | yes/no            |  55272 | 500 Internal Server Error for URL Containing Null  |
| `caddy#7737`     | yes/yes            |  38492 | yes/yes          |  39982 | yes/yes           |  33553 | Dynamic http3 upstreams recieve untemplated sni    |
| `caddy#7920`     | yes/yes            |  61504 | yes/yes          |  86828 | yes/yes           | 137719 | mTLS on wildcard also enables mTLS on specific sub |
| `GraphQLSP#144`  | yes/yes            |  41837 | yes/yes          |  35959 | yes/yes           |  53482 | Support client-only directives                     |
| `gql.tada#409`   | yes/yes            |  33521 | no/no            |  82490 | yes/yes           |  69618 | gql.tada turbo does not regenerate cache file when |
| `pow#247`        | yes/yes            |  62029 | yes/yes          |  54409 | yes/yes           |  75974 | API integration guide                              |
| `gql.tada#400`   | yes/yes            |  25938 | yes/yes          |  36470 | yes/yes           |  34268 | Incompatibility with urql since v1.8.8             |
| `certmagic#382`  | yes/yes            |  28753 | yes/yes          |  29443 | yes/yes           |  24518 | Preserve DNS provider metadata for DNS-01 cleanup  |
| `caddy#7617`     | yes/yes            |  67555 | yes/yes          | 308972 | yes/yes           | 242939 | TLS_ALPN challenge doesn't get disabled by Caddyfi |

### Tool use, per task

| Task             | without                               | local                                                 | primed                                |
| ---------------- | ------------------------------------- | ----------------------------------------------------- | ------------------------------------- |
| `GraphQLSP#126`  | Bash:12 Read:3 Edit:2 Grep:1          | Bash:16 Read:5 ws:search:3 Edit:2 Grep:1              | Bash:13 Edit:5 Read:3 Grep:2          |
| `caddy#7532`     | Bash:21 Read:16 Grep:4 Edit:1         | Bash:35 Read:11 ws:search:3 Edit:1 ws:refs:1 ws:why:1 | Bash:25 Read:7 Grep:3 Edit:1          |
| `caddy#7782`     | Bash:7 Read:4 Grep:2 Edit:1           | Bash:4 Grep:2 Read:2 Edit:1 ws:search:1               | Bash:3 Grep:2 Read:2 Edit:1           |
| `caddy#7894`     | Bash:4 Grep:4 Read:4 Edit:3           | Bash:10 Read:9 Edit:3 Grep:3 ws:search:1 ws:why:1     | Bash:26 Edit:5 Grep:4 Read:3          |
| `pow_assent#104` | Bash:9 Read:3 Edit:2 Grep:1           | Bash:14 ws:search:2 Edit:1 Read:1                     | Bash:8 Read:4 Edit:1                  |
| `pow#473`        | Bash:19 Read:2 Edit:1 Grep:1          | Bash:16 Read:7 Edit:1 Grep:1 ws:search:1              | Bash:19 Edit:9 Read:8 Grep:1          |
| `caddy#6312`     | Bash:12 Edit:4 Grep:1 Read:1          | Bash:11 Edit:7 Grep:3 Read:2 ws:search:1              | Bash:21 Edit:4 Grep:2 Read:2          |
| `pow#119`        | Bash:12 Read:10 Edit:2 Grep:1         | Bash:14 Read:9 Edit:3 Grep:1 ws:refs:1 ws:search:1    | Bash:22 Read:19 Grep:3 Edit:1         |
| `pow_assent#129` | Bash:20 Read:5 Edit:4 Grep:1          | Bash:31 Read:9 ws:search:4 Edit:3 Grep:1              | Bash:71 Read:19 Edit:4 Grep:3 Glob:1  |
| `gql.tada#368`   | Bash:40 Read:8 Edit:3                 | Bash:48 Read:6 ws:search:2 Edit:1                     | Bash:50 Read:7 Write:4 Edit:1         |
| `xcaddy#281`     | Bash:5 Read:3 Grep:2 Edit:1           | Bash:7 Read:3 Edit:1 Grep:1 ws:search:1 ws:why:1      | Bash:11 Read:3 Edit:1                 |
| `pow_assent#143` | Bash:15 Read:4 Edit:3 Write:1         | Bash:15 Read:7 Edit:6 Grep:2 Write:1 ws:search:1      | Bash:23 Read:10 Edit:2 Grep:1 Write:1 |
| `pow#709`        | Bash:11 Read:7 Grep:3 Edit:1          | Bash:16 Edit:2 ws:search:2 Read:1 ws:refs:1           | Bash:25 Read:2 Edit:1                 |
| `caddy#7898`     | Bash:12 Read:7 Grep:5 Edit:4          | Bash:12 Read:6 Edit:3 Grep:1 ws:search:1 ws:why:1     | Bash:9 Read:7 Edit:3 Grep:3           |
| `pow#71`         | Bash:11 Read:4 Edit:2 Grep:2          | Bash:5 Edit:2 ws:search:2 Read:1                      | Bash:7 Read:6 Edit:2                  |
| `caddy#7017`     | Bash:11 Grep:4 Read:4 Edit:3          | Bash:11 Read:4 Grep:3 Edit:1 ws:search:1 ws:why:1     | Bash:16 Read:5 Edit:1 Grep:1          |
| `caddy#7737`     | Bash:13 Read:5 Grep:4 Edit:2          | Bash:17 Edit:2 Read:2 Grep:1 ws:search:1              | Bash:13 Read:3 Edit:2 Grep:2          |
| `caddy#7920`     | Bash:26 Edit:5                        | Bash:22 Read:11 Edit:5 Grep:3 ws:search:2             | Bash:21 Read:17 Edit:8 Grep:6 Write:2 |
| `GraphQLSP#144`  | Bash:17 Read:3 Edit:2 Grep:2          | Bash:8 Read:4 Edit:2 Grep:1 ws:search:1               | Bash:19 Read:5 Grep:3 Edit:2          |
| `gql.tada#409`   | Bash:11 Read:4 Edit:3 Grep:3          | Bash:23 Read:7 Grep:3 ws:search:2 Edit:1              | Bash:16 Read:6 Edit:3 Grep:3          |
| `pow#247`        | Read:13 Bash:10 Edit:1 Grep:1 Write:1 | Bash:12 Grep:3 ws:search:2 Edit:1 Read:1 Write:1      | Bash:31 Read:8 Edit:1                 |
| `gql.tada#400`   | Bash:9 Grep:2 Edit:1                  | Bash:12 Edit:2 Read:1 ws:search:1                     | Bash:12 Edit:1 Grep:1 Read:1          |
| `certmagic#382`  | Bash:15 Edit:7 Grep:1                 | Edit:8 Bash:6 Read:3 ws:search:1                      | Bash:10 Edit:7 Read:1                 |
| `caddy#7617`     | Bash:28 Grep:5                        | Bash:64 Read:37 Grep:4 ws:search:3 Edit:2 ws:why:2    | Bash:46 Read:34 Grep:15 Edit:3        |
