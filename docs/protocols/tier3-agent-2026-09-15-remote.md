# Tier 3, with an agent — does it finish the work with less?

_2026-09-15 11:09, thulr `28d86fb`, 24 tasks, 217 min._

## Conditions

- One real agent, the same on all three arms, given a real issue and
  the repository **at the commit before the fix**.
- Every arm keeps every ordinary tool; two of them add thulr over
  MCP and take nothing away — a developer with it still has grep.
- `local` and `remote` differ in **nothing but the embedder**: the
  shipped default against a hosted one, same code, same evening.
- Graded against the diff the maintainers merged, in the parent's
  line numbers so the two are comparable.
- Tools each arm actually had, as the agent reported at startup: without **6**, local **9**, remote **9**.

## The gate, declared before the run

`remote` lands on the same lines at least as often as `without`
and spends fewer tokens — counted in **paired** tasks, not in a
mean, because one control that thrashes carries a mean on its own.
And it beats `local`: if the stronger index changes nothing the
agent does, then search quality is not what was holding it back.

## Results

|                 |  without |    local |   remote |
| --------------- | -------: | -------: | -------: |
| same file       | 23 of 24 | 24 of 24 | 23 of 24 |
| **same lines**  |   **20** |   **22** |   **21** |
| edited anything |       24 |       24 |       24 |
| mean tokens     |    45396 |    60501 |    48021 |
| mean turns      |       21 |       25 |       21 |
| mean seconds    |      152 |      204 |      137 |
| total cost      |   $21.26 |   $31.78 |   $22.03 |

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

| Tool        | without | local | remote |
| ----------- | ------: | ----: | -----: |
| `Bash`      |    13.2 |  14.6 |   13.0 |
| `Read`      |     3.9 |   5.2 |    3.6 |
| `Edit`      |     2.0 |   1.9 |    1.9 |
| `Grep`      |     1.5 |   1.2 |    0.8 |
| `ws:search` |     0.0 |   1.2 |    1.0 |
| `Write`     |     0.2 |   0.2 |    0.1 |
| `ws:why`    |     0.0 |   0.1 |    0.0 |
| `ws:refs`   |     0.0 |   0.1 |    0.0 |
| `Glob`      |     0.0 |   0.0 |    0.0 |

## Raw rows

Transcripts are kept beside the corpus cache, not in this repository.

| Task             | without: file/line | tokens | local: file/line | tokens | remote: file/line | tokens | issue                                               |
| ---------------- | ------------------ | -----: | ---------------- | -----: | ----------------- | -----: | --------------------------------------------------- |
| `wonka#141`      | yes/yes            |  50661 | yes/yes          |  38596 | yes/yes           |  60883 | `dist/wonka.d.ts` failing typecheck on TS 4.9.3+    |
| `gql.tada#295`   | yes/yes            |  15761 | yes/yes          |  27498 | yes/yes           |  20121 | Schema is missing a `schema` property               |
| `pow#632`        | yes/yes            |  28260 | yes/yes          |  54289 | yes/yes           |  34523 | Usage of Conn in 'before_process'                   |
| `gql.tada#270`   | yes/yes            |   9766 | yes/yes          |  17305 | yes/yes           |  12447 | tadaTurboLocation and tadaPersistedLocation are no  |
| `pow#224`        | yes/yes            |  58105 | yes/yes          |  99476 | yes/yes           |  74244 | Password reset edit route note found when submitti  |
| `caddy#7567`     | yes/yes            | 114634 | yes/yes          |  66509 | yes/yes           |  62761 | Regression for wildcard `tls get_certificate http`  |
| `xcaddy#47`      | yes/no             |  34678 | yes/yes          |  42845 | yes/no            |  44246 | Build fails under go1.16                            |
| `GraphQLSP#195`  | yes/yes            |  17591 | yes/yes          |  21226 | yes/yes           |  20274 | Support providing more built-in keys for \`field-us |
| `GraphQLSP#40`   | yes/yes            |  26161 | yes/yes          |  30194 | yes/yes           |  38586 | When updating the operationName it appends a new \` |
| `gql.tada#449`   | yes/yes            |  48734 | yes/yes          |  43848 | yes/yes           |  70657 | The parser hangs indefinitely when a GraphQL query  |
| `caddy#7698`     | yes/yes            |  16278 | yes/yes          |  31595 | yes/yes           |  43900 | Set `http.auth.user` variables even on unsuccessfu  |
| `pow#161`        | yes/yes            |  50857 | yes/yes          |  64560 | yes/yes           |  47325 | Users can change their e-mail to one that's alread  |
| `xcaddy#281`     | yes/no             |  27485 | yes/no           |  31458 | yes/no            |  36228 | Error: unknown flag: --config on `xcaddy run`       |
| `caddy#7715`     | yes/yes            |  38401 | yes/yes          |  41360 | yes/yes           |  42496 | "invalid Read on closed Body" when using reverse_p  |
| `xcaddy#238`     | yes/yes            |  36963 | yes/yes          |  57766 | yes/yes           |  54648 | xcaddy does not download newly published module ve  |
| `gql.tada#400`   | yes/no             |  22510 | yes/yes          |  43040 | yes/yes           |  42255 | Incompatibility with urql since v1.8.8              |
| `hoofd#76`       | yes/yes            |  23840 | yes/yes          |  35343 | yes/yes           |  22915 | Failure when trying to `removeChild` that doesn't   |
| `wonka#168`      | yes/yes            |  45171 | yes/yes          |  50541 | yes/yes           |  25231 | Typescript errors in wonka 6.3.3                    |
| `caddy#7532`     | yes/yes            |  38364 | yes/yes          |  37301 | yes/yes           |  38949 | Caddy 2.11 HTTP 403 error via docker exec caddy re  |
| `pow_assent#129` | no/no              | 154170 | yes/yes          | 320369 | no/no             | 121154 | Switching OAuth provider when the user_id field is  |
| `caddy#7920`     | yes/yes            |  85461 | yes/yes          | 103125 | yes/yes           |  85078 | mTLS on wildcard also enables mTLS on specific sub  |
| `GraphQLSP#82`   | yes/yes            |  28346 | yes/no           |  84885 | yes/yes           |  39801 | Investigate bug where fragment-renaming gets wrong  |
| `gql.tada#551`   | yes/yes            |  88906 | yes/yes          |  62700 | yes/yes           |  76146 | bug: large set of unions not working                |
| `caddy#7265`     | yes/yes            |  28405 | yes/yes          |  46209 | yes/yes           |  37658 | Option to enable trusted_proxies for unix socket f  |

### Tool use, per task

| Task             | without                              | local                                                | remote                                             |
| ---------------- | ------------------------------------ | ---------------------------------------------------- | -------------------------------------------------- |
| `wonka#141`      | Bash:32 Edit:1 Grep:1 Read:1         | Bash:26 Edit:1                                       | Bash:25 Read:2 Edit:1 Grep:1 ws:search:1           |
| `gql.tada#295`   | Bash:4 Edit:3 Read:3 Grep:2          | Bash:8 Read:3 Edit:2 ws:search:1                     | Bash:4 Edit:1 Grep:1 Read:1 ws:search:1            |
| `pow#632`        | Bash:8 Read:6 Edit:3 Grep:2          | Bash:14 Read:5 Grep:3 Edit:2 ws:search:2 ws:why:1    | Bash:12 Read:5 Edit:3 Grep:2 ws:search:2 ws:refs:1 |
| `gql.tada#270`   | Bash:2 Edit:1 Grep:1 Read:1          | Bash:3 Edit:1 Read:1 ws:refs:1 ws:search:1           | Bash:1 Edit:1 Read:1 ws:search:1                   |
| `pow#224`        | Bash:21 Read:7 Edit:1                | Read:22 Bash:19 Edit:1 Grep:1 ws:search:1 ws:why:1   | Bash:25 Read:9 Edit:1 ws:search:1                  |
| `caddy#7567`     | Bash:21 Read:5 Edit:2                | Bash:17 Grep:5 Read:5 Edit:2 ws:search:1             | Bash:19 Read:5 Edit:2 Grep:2 ws:search:1 ws:why:1  |
| `xcaddy#47`      | Bash:5 Read:3 Edit:1                 | Bash:6 Read:4 ws:search:2 Edit:1                     | Bash:6 Read:4 Edit:1 ws:search:1                   |
| `GraphQLSP#195`  | Edit:4 Bash:3 Grep:3 Read:2          | Edit:5 Read:4 Bash:3 Grep:3 ws:search:1              | Bash:7 Edit:5 Grep:2 Read:2 ws:search:1            |
| `GraphQLSP#40`   | Bash:4 Read:3 Grep:2 Edit:1          | Bash:5 Read:2 Edit:1 Grep:1 ws:search:1              | Bash:10 Read:2 Edit:1 ws:search:1                  |
| `gql.tada#449`   | Bash:20 Grep:3 Edit:2 Read:2         | Bash:16 Edit:2 Read:2 Grep:1 ws:search:1             | Bash:30 Read:3 Edit:2 ws:search:1                  |
| `caddy#7698`     | Edit:5 Bash:4 Read:3 Grep:1          | Bash:6 Edit:2 Glob:1 Read:1 ws:search:1              | Bash:5 Edit:2 Read:2 Glob:1 ws:search:1            |
| `pow#161`        | Bash:12 Read:12 Edit:1 Grep:1        | Bash:15 Read:10 Edit:2 Grep:1 ws:search:1            | Bash:12 Read:5 Edit:2 ws:search:1                  |
| `xcaddy#281`     | Bash:5 Grep:4 Read:3 Edit:1          | Bash:6 Read:3 Grep:2 Edit:1 ws:search:1              | Bash:11 Read:2 Edit:1 ws:search:1                  |
| `caddy#7715`     | Bash:9 Read:3 Edit:1 Grep:1          | Bash:13 Read:5 Edit:1 ws:search:1                    | Bash:6 Read:2 Edit:1 Grep:1 ws:search:1            |
| `xcaddy#238`     | Bash:9 Read:4 Edit:1 Grep:1          | Bash:9 Read:5 Edit:1 ws:search:1                     | Bash:11 Read:4 Grep:2 Edit:1 ws:search:1           |
| `gql.tada#400`   | Bash:8 Edit:1 Write:1                | Bash:17 Edit:1 Grep:1 Read:1 Write:1 ws:search:1     | Bash:19 Edit:1 Read:1 ws:search:1                  |
| `hoofd#76`       | Bash:8 Read:4 Edit:1 Grep:1          | Bash:9 Read:4 Edit:1 Grep:1 ws:search:1 ws:why:1     | Bash:5 Read:3 Edit:1 Grep:1                        |
| `wonka#168`      | Bash:26 Edit:2                       | Bash:20 Read:4 Edit:2 ws:search:1                    | Bash:13 Edit:2                                     |
| `caddy#7532`     | Bash:12 Grep:4 Read:3 Edit:1         | Bash:11 Read:5 Edit:1 Grep:1 ws:search:1             | Bash:7 Read:5 Grep:2 Edit:1 ws:search:1            |
| `pow_assent#129` | Bash:34 Read:5 Edit:2 Grep:1         | Bash:61 Read:18 Edit:4 ws:search:3 Write:2 ws:refs:1 | Bash:25 Read:9 Edit:3 Grep:1 ws:search:1           |
| `caddy#7920`     | Bash:22 Read:10 Edit:6 Grep:2        | Bash:17 Grep:8 Read:8 Edit:3 ws:search:1             | Bash:19 Edit:6 Read:6 ws:search:2 Grep:1 Write:1   |
| `GraphQLSP#82`   | Bash:8 Read:4 Grep:2 Edit:1          | Bash:11 Read:5 Edit:3 Grep:2 ws:search:2             | Bash:7 Read:4 ws:search:2 Edit:1 Grep:1            |
| `gql.tada#551`   | Bash:33 Read:5 Write:3 Edit:2 Grep:1 | Bash:27 Read:3 Edit:1 Write:1 ws:search:1            | Bash:24 Read:6 Edit:1 Grep:1 Write:1 ws:search:1   |
| `caddy#7265`     | Bash:7 Read:4 Edit:3 Grep:3          | Bash:12 Edit:5 Read:5 ws:search:2                    | Bash:8 Edit:5 Read:4 Grep:2 ws:search:1            |
