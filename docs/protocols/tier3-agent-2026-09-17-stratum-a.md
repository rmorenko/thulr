# Tier 3, with an agent — does it finish the work with less?

_2026-09-17 07:17, wsindex `bc1d39f`, 75 tasks, 379 min._

## Conditions

- One real agent, the same on all three arms, given a real issue and
  the repository **at the commit before the fix**.
- Every arm keeps every ordinary tool; two of them add wsindex over
  MCP and take nothing away — a developer with it still has grep.
- `local` and `primed` read **the same index**, so what differs
  between them is delivery: one is a server the agent may call, the
  other is five ranked locations handed over in the task itself.
- Graded against the diff the maintainers merged, in the parent's
  line numbers so the two are comparable.
- One repository per task — the shape where grep is strongest and this tool weakest. Named because the premise is several.
- Tools each arm actually had, as the agent reported at startup: without **6**, local **9**.

## The gate, declared before the run

The arm with wsindex is **ruined** less often than the one without
it, counted in paired tasks. Ruined is a miss or more than 130,000
tokens — a composite fixed before the run, at three times the median
of the twenty-four-task run that preceded it.

A mean cannot answer this. Averaged over mixed tasks the tool costs
more and finds the same, which is what four runs have now said. The
claim left standing is narrower and about a tail: that where ripgrep
*drowns* — more than twenty files, median sixty-five here — the
control sometimes ends up wrong or ruined and the treatment does
not. Two such cases were seen in twenty-four random tasks, at
241 814 and 259 155 tokens, both missing. Random sampling cannot
measure an event that rare, so this run is not random: every task
in it is one ripgrep already drowned on, selected by the control's
own behaviour and graded against the pull request, with wsindex
touching neither end of that.

## Results

| | without | local |
| --- | ---: | ---: |
| same file | 74 of 75 | 72 of 75 |
| **same lines** | **60** | **63** |
| edited anything | 75 | 75 |
| mean tokens | 43363 | 48558 |
| mean turns | 23 | 23 |
| mean seconds | 147 | 147 |
| total cost | $68.36 | $74.30 |
| **ruined** | **16** | **13** |

**What this does not say.** Whether the fix *works* is not measured:
that needs the project's own tests, and thirty-three repositories
across seven languages do not have a suite this can run. Landing on
the same lines is more than finding the file and less than fixing
the bug, and the gap between those is the agent's judgement, which
is the same on every arm here.

## What the agent actually called

Mean calls per task. The question this answers is whether the
treatment *replaced* any reading or merely added to it — the first
run of this harness found wsindex called once a task on top of an
unchanged amount of grep, which costs and saves nothing.

| Tool | without | local |
| --- | ---: | ---: |
| `Bash` | 14.6 | 12.7 |
| `Read` | 3.3 | 3.8 |
| `Edit` | 2.5 | 2.9 |
| `Grep` | 1.4 | 1.4 |
| `ws:search` | 0.0 | 0.9 |
| `Write` | 0.2 | 0.2 |
| `ws:refs` | 0.0 | 0.1 |
| `ws:why` | 0.0 | 0.1 |
| `Glob` | 0.0 | 0.0 |

## Raw rows

Transcripts are kept beside the corpus cache, not in this repository.

| Task | without: file/line | tokens | local: file/line | tokens | issue |
| --- | --- | ---: | --- | ---: | --- |
| `gql.tada#286` | yes/yes | 34568 | yes/yes | 25149 | `generate output` doesn't seem to work by default  |
| `pow#292` | yes/yes | 102762 | yes/yes | 76736 | Keeping scope in generated routes |
| `GraphQLSP#333` | yes/yes | 41184 | yes/yes | 51486 | Schema name is not computed when using multiple sc |
| `caddy#7727` | yes/yes | 18426 | yes/yes | 33672 | Client TLS not working on v2.11.3 |
| `caddy#7534` | yes/yes | 13176 | yes/yes | 26877 | tls_client_subject set to literal `{http.request.t |
| `caddy#7433` | yes/no | 65380 | yes/yes | 62175 | caddy fmt does not format multi-line strings prope |
| `pow#602` | yes/yes | 7881 | yes/yes | 10572 | Switch to :crypto.mac/4 from :crypto.hmac/3 |
| `gql.tada#32` | yes/yes | 63868 | yes/yes | 34752 | RFC: allow reacting to client-side directives |
| `xcaddy#117` | yes/yes | 33210 | yes/yes | 39387 | xcaddy run with go 19 does not work |
| `caddy#7335` | yes/yes | 24535 | yes/yes | 31365 | log _subdirectory_ permissions |
| `GraphQLSP#82` | yes/yes | 52347 | yes/no | 55622 | Investigate bug where fragment-renaming gets wrong |
| `GraphQLSP#126` | yes/yes | 19100 | yes/yes | 72403 | GraphQL field descriptions in IntelliSense have br |
| `pow#161` | yes/yes | 52268 | yes/yes | 48996 | Users can change their e-mail to one that's alread |
| `caddy#7017` | yes/yes | 21821 | yes/no | 49127 | 500 Internal Server Error for URL Containing Null  |
| `caddy#7898` | yes/yes | 33844 | yes/yes | 33301 | Nested named route invocation undetected |
| `gql.tada#377` | yes/yes | 90925 | yes/yes | 94800 | Issue: Explicit type annotation is needed when ini |
| `caddy#7907` | yes/yes | 40199 | yes/yes | 48277 | Caddy 2.8.4: uri replace does not work for %29 |
| `ingress#249` | yes/yes | 33374 | yes/yes | 39998 | Add trusted_proxies annotation |
| `gql.tada#516` | yes/yes | 202235 | yes/yes | 112818 | tada warns when using subpath imports |
| `certmagic#404` | yes/no | 35337 | yes/no | 34549 | Decouple cleanup context from obtaining context |
| `wonka#149` | yes/no | 15334 | yes/no | 24864 | Narrowing overload for `filter` |
| `pow_assent#143` | yes/no | 78289 | yes/yes | 68266 | PowAssent for Phoenix API and SPA / mobile app |
| `caddy#7670` | yes/yes | 25813 | no/no | 98628 | Managed ECH HTTPS records omit ALPN, causing clien |
| `pow_assent#129` | yes/yes | 117954 | yes/yes | 177848 | Switching OAuth provider when the user_id field is |
| `caddy#7782` | yes/yes | 12023 | yes/yes | 13158 | http.request.proto is wonky for HTTP/2 and HTTP/3  |
| `xcaddy#93` | yes/yes | 25180 | yes/yes | 40430 | xcaddy doesn't build specified version |
| `xcaddy#213` | yes/yes | 6668 | yes/yes | 9820 | Error with compiling custom Caddy with version 0.4 |
| `GraphQLSP#235` | yes/no | 50765 | yes/yes | 74007 | Build support for tanstack-query in unused-fields |
| `xcaddy#182` | yes/no | 10116 | yes/yes | 34328 | xcaddy v0.3.5 vs v0.4.0 = 15mb increase in filesiz |
| `pow#88` | yes/yes | 57927 | no/no | 110592 | Pow.Store.Backend.EtsCache not being started autom |
| `xcaddy#51` | yes/yes | 27374 | yes/yes | 22877 | Can't do module replacement with github forks |
| `xcaddy#281` | yes/no | 25532 | yes/no | 25355 | Error: unknown flag: --config on `xcaddy run` |
| `certmagic#382` | yes/yes | 20430 | yes/yes | 33357 | Preserve DNS provider metadata for DNS-01 cleanup |
| `GraphQLSP#193` | yes/no | 12056 | yes/no | 21138 | Add bail logic to the introspection-polling |
| `gql.tada#298` | yes/yes | 92769 | yes/yes | 102794 | `turbo` cache is not including fragments that are  |
| `forwardproxy#149` | yes/no | 23036 | yes/yes | 29966 | insecure schemes are only allowed to localhost ups |
| `GraphQLSP#39` | yes/yes | 69193 | yes/yes | 55626 | Hoist the `typescript` types |
| `forwardproxy#47` | yes/yes | 25033 | yes/yes | 28441 | High amount of unclosed abandoned connections |
| `caddy#7945` | yes/yes | 52176 | yes/yes | 60120 | Access log writes status code 200 on timeout even  |
| `caddy#7715` | yes/yes | 47418 | yes/yes | 54825 | "invalid Read on closed Body" when using reverse_p |
| `gql.tada#340` | yes/yes | 34396 | yes/yes | 62085 | `gql.tada` not updating types on `schema.graphql`  |
| `caddy#7780` | yes/yes | 47893 | yes/yes | 33730 | Incorrect error message on duplicate request match |
| `gql.tada#511` | yes/no | 99652 | yes/no | 117060 | RFC: `graphql.frag` helper |
| `pow#391` | yes/yes | 18654 | yes/yes | 21094 | "password_hash can't be blank" error when trying t |
| `GraphQLSP#322` | yes/no | 108781 | yes/yes | 55962 | Unknown fragment error when the fragment is define |
| `pow_assent#50` | yes/yes | 73910 | yes/no | 26332 | Error in user changeset |
| `pow#364` | yes/yes | 20451 | yes/yes | 62998 | nil user_id causes app failure |
| `pow_assent#180` | yes/yes | 32868 | yes/yes | 83981 | Warning from dialyzer : Invalid type specification |
| `caddy#7532` | yes/yes | 13398 | yes/yes | 44469 | Caddy 2.11 HTTP 403 error via docker exec caddy re |
| `caddy#6312` | yes/yes | 14018 | yes/yes | 32786 | http/3 support in reverse_proxy module |
| `xcaddy#69` | yes/yes | 32216 | yes/yes | 29242 | xcaddy development mode fails if 'go.mod' includes |
| `pow#649` | yes/yes | 60688 | yes/yes | 63748 | Phoenix 1.6 support? |
| `caddy#7458` | yes/yes | 24813 | yes/yes | 28623 | Global `dns` option discrepancy between docs and b |
| `pow_assent#73` | yes/yes | 10740 | yes/yes | 10308 | `:httpc` missing in default elixir 1.9 mix release |
| `pow#201` | yes/yes | 30142 | yes/yes | 35915 | Unable to use 'Pow.Plug.authenticate_user(conn, pa |
| `GraphQLSP#42` | yes/no | 59595 | yes/yes | 67044 | Add component fragment spread diagnostic |
| `assent#124` | yes/yes | 44950 | no/no | 43311 | Add connection pool to Mint HTTP adapter (turn it  |
| `caddy#7617` | yes/yes | 68497 | yes/yes | 116291 | TLS_ALPN challenge doesn't get disabled by Caddyfi |
| `pow#119` | no/no | 34049 | yes/yes | 76733 | POW custom routes don't seem to work? |
| `caddy#7920` | yes/yes | 44036 | yes/yes | 52159 | mTLS on wildcard also enables mTLS on specific sub |
| `caddy#7409` | yes/yes | 19353 | yes/yes | 23516 | Feature request: Add flag for json output |
| `gql.tada#295` | yes/yes | 11750 | yes/yes | 20141 | Schema is missing a `schema` property |
| `GraphQLSP#144` | yes/yes | 46687 | yes/yes | 31136 | Support client-only directives |
| `caddy#7502` | yes/yes | 36928 | yes/yes | 24672 | Unexpected automatic redirection |
| `pow_assent#110` | yes/yes | 50502 | yes/yes | 38741 | Redirect to original request path after auth |
| `GraphQLSP#87` | yes/yes | 22091 | yes/yes | 22417 | Support additional headers for introspection |
| `gql.tada#449` | yes/yes | 40421 | yes/yes | 46612 | The parser hangs indefinitely when a GraphQL query |
| `caddy#7737` | yes/yes | 52604 | yes/yes | 38080 | Dynamic http3 upstreams recieve untemplated sni |
| `wonka#168` | yes/yes | 52532 | yes/yes | 46144 | Typescript errors in wonka 6.3.3 |
| `forwardproxy#63` | yes/yes | 23564 | yes/yes | 18743 | Caddy's import path has changed |
| `wonka#159` | yes/yes | 34635 | yes/yes | 50511 | Top-level declarations in .d.ts files must start w |
| `pow_assent#179` | yes/no | 76380 | yes/yes | 55472 | Handle User Rejecting Permissions |
| `pow#21` | yes/yes | 53185 | yes/no | 50151 | allow mapping password_hash to another field? |
| `database_cleaner#681` | yes/no | 16207 | yes/yes | 15666 | Poor strategy class lookup |
| `pow#71` | yes/yes | 60184 | yes/yes | 27501 | Disable registration routes |

### Tool use, per task

| Task | without | local |
| --- | --- | --- |
| `gql.tada#286` | Bash:9 Read:7 Grep:2 Edit:1 | Bash:6 Read:4 Edit:1 Grep:1 ws:search:1 ws:why:1 |
| `pow#292` | Bash:23 Read:6 Edit:2 Grep:1 | Bash:20 Edit:3 Read:2 ws:search:2 ws:why:1 |
| `GraphQLSP#333` | Bash:12 Read:7 Grep:2 Edit:1 | Bash:14 Read:5 Grep:2 Edit:1 ws:search:1 |
| `caddy#7727` | Bash:7 Grep:2 Edit:1 Read:1 | Bash:16 Edit:1 Grep:1 |
| `caddy#7534` | Bash:4 Grep:2 Edit:1 Read:1 | Grep:5 Bash:4 Read:2 Edit:1 ws:search:1 |
| `caddy#7433` | Bash:19 Read:7 Edit:2 Write:2 Grep:1 | Bash:12 Write:3 Edit:2 Read:1 ws:search:1 |
| `pow#602` | Bash:3 Edit:1 Grep:1 Read:1 | Bash:2 Grep:2 Edit:1 Read:1 |
| `gql.tada#32` | Bash:20 Read:4 Edit:3 Write:1 | Bash:11 Edit:3 Read:3 Grep:1 Write:1 ws:search:1 |
| `xcaddy#117` | Bash:7 Read:3 Grep:2 Edit:1 | Bash:7 Read:2 Edit:1 ws:search:1 |
| `caddy#7335` | Bash:7 Edit:4 Grep:1 Read:1 | Bash:5 Edit:5 Grep:2 Read:2 ws:search:1 |
| `GraphQLSP#82` | Bash:11 Read:8 Grep:4 Edit:1 | Bash:11 Read:7 Edit:3 Grep:1 ws:search:1 |
| `GraphQLSP#126` | Bash:6 Edit:2 Grep:2 Read:2 | Bash:22 Edit:6 Read:5 Grep:3 ws:search:2 ws:why:1 |
| `pow#161` | Bash:19 Edit:2 Grep:2 | Bash:13 Read:8 Edit:2 ws:search:1 |
| `caddy#7017` | Bash:9 Edit:2 Grep:1 | Bash:9 Read:4 Grep:3 Edit:1 ws:search:1 |
| `caddy#7898` | Bash:16 Edit:4 Read:1 | Bash:7 Edit:3 Grep:2 Read:1 ws:search:1 |
| `gql.tada#377` | Bash:39 Edit:3 Grep:3 Read:3 | Bash:33 Edit:9 Read:2 Write:1 ws:search:1 |
| `caddy#7907` | Bash:10 Grep:3 Edit:1 Read:1 | Bash:7 Read:5 Grep:3 Edit:1 Glob:1 ws:search:1 |
| `ingress#249` | Bash:15 Read:8 Edit:2 Grep:1 | Bash:13 Edit:5 Grep:4 Read:3 ws:search:1 |
| `gql.tada#516` | Bash:92 Read:10 Grep:7 Edit:2 Write:2 | Bash:14 Read:12 Grep:4 Edit:2 ws:search:2 |
| `certmagic#404` | Bash:10 Read:8 Grep:2 Edit:1 | Bash:4 Grep:4 Read:3 Edit:1 ws:search:1 ws:why:1 |
| `wonka#149` | Bash:16 Edit:1 Grep:1 | Bash:17 Edit:1 Grep:1 Read:1 Write:1 |
| `pow_assent#143` | Bash:11 Read:10 Edit:6 Write:1 | Bash:10 Read:7 Edit:2 ws:search:2 Write:1 |
| `caddy#7670` | Bash:8 Edit:2 Read:1 | Bash:14 Read:11 Edit:8 Grep:7 ws:refs:1 ws:search:1 |
| `pow_assent#129` | Bash:30 Read:5 Edit:1 Grep:1 Write:1 | Bash:50 Read:6 ws:search:2 Edit:1 Write:1 ws:refs:1 |
| `caddy#7782` | Bash:3 Edit:2 Grep:2 Read:1 | Bash:2 Edit:2 Grep:2 Read:1 |
| `xcaddy#93` | Bash:4 Edit:4 Read:3 Grep:1 | Bash:4 Edit:4 Read:3 ws:search:1 |
| `xcaddy#213` | Bash:3 Edit:1 | Bash:6 Edit:1 Read:1 |
| `GraphQLSP#235` | Bash:21 Read:6 Edit:1 Grep:1 Write:1 | Bash:19 Edit:3 Read:1 Write:1 ws:search:1 |
| `xcaddy#182` | Bash:4 Read:2 Edit:1 Grep:1 | Bash:6 Read:3 Edit:2 Grep:1 ws:search:1 |
| `pow#88` | Bash:26 Read:4 Edit:3 Grep:1 Write:1 | Bash:37 Read:9 ws:refs:2 ws:search:2 Edit:1 |
| `xcaddy#51` | Bash:3 Read:3 Edit:2 Grep:2 | Bash:6 Edit:2 Read:1 ws:search:1 |
| `xcaddy#281` | Bash:4 Read:4 Edit:1 Grep:1 | Bash:4 Read:3 Edit:1 Grep:1 ws:search:1 |
| `certmagic#382` | Edit:7 Bash:5 Grep:3 Read:1 | Bash:11 Edit:8 Grep:2 Read:2 ws:search:1 |
| `GraphQLSP#193` | Bash:3 Edit:2 Grep:1 Read:1 | Edit:4 Bash:3 Read:3 Grep:1 ws:search:1 |
| `gql.tada#298` | Bash:46 Read:6 Grep:4 Edit:1 | Bash:39 Read:9 Grep:3 Edit:1 ws:search:1 |
| `forwardproxy#149` | Bash:5 Edit:4 Read:4 Grep:3 | Bash:9 Read:7 Edit:5 Grep:3 ws:refs:1 ws:why:1 |
| `GraphQLSP#39` | Bash:24 Edit:10 Read:1 Write:1 | Bash:17 Edit:7 Read:3 Grep:2 ws:search:1 |
| `forwardproxy#47` | Bash:7 Edit:3 Grep:2 Read:1 | Bash:3 Edit:3 Grep:1 Read:1 ws:search:1 |
| `caddy#7945` | Bash:11 Read:5 Edit:2 Grep:2 | Bash:14 Edit:5 Read:3 Grep:2 Glob:1 ws:search:1 |
| `caddy#7715` | Bash:18 Edit:3 Read:1 | Read:6 Bash:5 Grep:3 Edit:1 ws:search:1 |
| `gql.tada#340` | Bash:13 Read:6 Edit:4 Grep:1 Write:1 | Bash:23 Read:6 Edit:4 Grep:4 ws:search:1 |
| `caddy#7780` | Bash:11 Grep:6 Read:3 Edit:1 | Bash:5 Read:3 Grep:2 Edit:1 ws:search:1 |
| `gql.tada#511` | Bash:39 Edit:5 Read:4 Write:2 | Bash:45 Edit:8 Read:5 Write:4 Grep:2 ws:refs:1 ws:search:1 |
| `pow#391` | Bash:4 Edit:2 Grep:2 Read:1 | Bash:4 Edit:2 Read:1 ws:search:1 |
| `GraphQLSP#322` | Bash:46 Read:5 Edit:3 Write:2 | Bash:18 Read:4 Edit:1 ws:search:1 |
| `pow_assent#50` | Bash:14 Read:7 Edit:1 | Bash:8 Edit:1 Grep:1 Read:1 ws:search:1 |
| `pow#364` | Bash:8 Read:2 Edit:1 Grep:1 | Bash:13 Read:8 Edit:2 Grep:1 ws:search:1 |
| `pow_assent#180` | Bash:12 Read:3 Edit:1 | Bash:18 Read:8 Grep:1 ws:search:1 |
| `caddy#7532` | Bash:6 Edit:1 | Bash:18 Read:7 Grep:3 Edit:1 |
| `caddy#6312` | Bash:7 Edit:4 | Bash:7 Edit:4 Read:1 ws:search:1 |
| `xcaddy#69` | Bash:4 Read:4 Edit:1 Grep:1 | Bash:9 Edit:1 Read:1 ws:search:1 |
| `pow#649` | Bash:17 Edit:4 | Bash:20 Read:5 Edit:2 Grep:1 |
| `caddy#7458` | Bash:6 Read:5 Edit:1 Grep:1 | Bash:8 Read:3 Edit:1 ws:refs:1 ws:search:1 |
| `pow_assent#73` | Bash:2 Edit:1 Grep:1 Read:1 | Read:2 Edit:1 Grep:1 |
| `pow#201` | Bash:16 Edit:2 Read:1 | Bash:11 Read:5 Edit:3 ws:search:1 |
| `GraphQLSP#42` | Bash:16 Edit:4 Read:4 | Bash:16 Edit:10 Read:2 Write:1 ws:search:1 |
| `assent#124` | Bash:15 Edit:7 Read:2 Write:1 | Bash:8 Read:3 Edit:1 ws:search:1 |
| `caddy#7617` | Bash:19 Read:6 Grep:4 Edit:2 | Bash:19 Read:8 Grep:6 Edit:3 ws:search:1 |
| `pow#119` | Bash:9 Read:5 Edit:4 | Bash:23 Read:12 Edit:4 ws:search:1 |
| `caddy#7920` | Bash:17 Edit:5 Read:5 Grep:3 | Bash:10 Edit:7 Read:4 Grep:2 ws:search:1 |
| `caddy#7409` | Bash:9 Edit:3 | Bash:8 Edit:4 Read:1 ws:search:1 |
| `gql.tada#295` | Bash:2 Grep:2 Read:2 Edit:1 | Bash:3 Read:3 Edit:2 Grep:2 ws:search:1 |
| `GraphQLSP#144` | Bash:12 Read:5 Edit:2 Write:1 | Bash:9 Read:3 Edit:2 Grep:1 Write:1 ws:search:1 |
| `caddy#7502` | Bash:11 Grep:4 Read:3 Edit:2 | Bash:9 Read:3 Edit:2 |
| `pow_assent#110` | Bash:18 Edit:8 Read:5 Grep:1 | Bash:8 Edit:4 Read:3 Grep:2 ws:search:1 |
| `GraphQLSP#87` | Edit:9 Bash:7 Read:4 Grep:1 | Bash:4 Edit:4 Read:4 ws:search:1 |
| `gql.tada#449` | Bash:18 Grep:3 Read:3 Edit:2 | Bash:11 Edit:2 Read:2 Grep:1 ws:search:1 |
| `caddy#7737` | Bash:15 Read:5 Grep:4 Edit:2 | Bash:7 Read:4 Edit:2 Grep:2 ws:search:1 |
| `wonka#168` | Bash:29 Edit:2 | Bash:25 Edit:2 Read:2 ws:search:1 |
| `forwardproxy#63` | Bash:11 Edit:1 Grep:1 | Bash:12 Read:2 Edit:1 |
| `wonka#159` | Bash:25 | Bash:22 Read:5 Edit:2 Write:1 ws:search:1 |
| `pow_assent#179` | Bash:34 Read:7 Edit:1 Grep:1 | Bash:22 Edit:5 Read:1 ws:search:1 |
| `pow#21` | Bash:12 Read:5 Grep:4 Edit:1 | Edit:10 Bash:7 Read:6 Grep:1 ws:refs:1 |
| `database_cleaner#681` | Bash:6 Edit:1 Grep:1 Read:1 | Bash:6 Edit:1 Read:1 ws:search:1 |
| `pow#71` | Bash:17 Edit:4 Read:2 | Bash:8 Read:4 Edit:3 Grep:2 ws:search:1 |
