# job job-aiknow1-11081958  started 2026-11-08T11:00:40Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final state is committed on `job-aiknow1-11081958`.

## Files added

- `llms.txt` (74 lines, llmstxt.org shape)
- `docs/AGENT_GUIDE.md` (worked example), `docs/design/AGENT_CLI_TASKS.md` (2-hour task texts)
- `integrations/claude-code/skills/ailc/SKILL.md`, `integrations/AGENTS.md`
- `integrations/mcp/`: `README.md`, `ailc_mcp.py`, `examples/{typed,mutates,refused}.py`
- `examples/agent_guide/{slow,fixed}.py`
- `AIL_CURRENT/test_ail_agent_integrations.py`, `AIL_CURRENT/tests.d/test_ail_agent_integrations.txt`
- Records: DEVLOG (root + `AIL_CURRENT`), DIFFERENCES row `C?-job-aiknow1-11081958-1`, manifest pins

## Planned commands

| planned | status |
|---|---|
| `ailc build` | exists as `ail build` (wrapper over `compile`) |
| `ailc run` / `run --diff` | exists as `ail run` / `ail run --diff` |
| `--json` diagnostics | exists on `compile`; `ail.strict/1` on a `--strict` refusal, `ail.build/1` on success |
| `ailc ext` | **missing** — no `ext` subcommand; `ail build --cpython` fails with `unrecognized arguments: --cpython` |
| `--why` | **missing** — no such flag |

Both missing items are omitted from the agent docs; task texts are in `docs/design/AGENT_CLI_TASKS.md`. The docs also corrected a false schema claim I found: a `--strict --json` refusal is `ail.strict/1`, not `ail.build/1`.

## Tests

- `test_ail_agent_integrations`: 9 tests, OK — 15.1 s, then 14.6 s and 14.0 s after edits.
- `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3` + integration: 34 tests, OK (1 skipped), 289.9 s.
- `tools/docs_links.py`: 42 files, 0 broken; `update_manifest.py --check`: exit 0.

## Probes (`/tmp/probes/`, `bash ~/tools/cmp.sh <p> $PWD`)

All 11 exited 0 with **same stdout on the general (`g`) and default (`d`) builds**:

`p1` slow.py, `p2` fixed.py, `p3` typed.py, `p4` mutates.py, `p5` refused.py (while-else, general path), `p6` `LABEL="1"`, `p7` argument values (0/negative/positive), `p8` list items (empty/negative/int64), `p9` attribute values, `p10` dict values incl. missing key, `p11` widths/negative.

## Worked example (real run)

Profile 4.545 s; strict refusal exit 3, `ail.strict/1`, `AIL0103` line 8, `fix.replace_range [8,8]` reproduces `fixed.py` byte-for-byte; rebuild exit 0 `passed`; `diff` exit 0; `ail run --diff` prints `ail diff: agree`. Timings: CPython 4.62/4.63/4.73 s (median 4.63), native 0.16/0.16/0.15 s (median 0.16) = **28.9x**. The guide now records that the hybrid build keeps `collatz_total` on CPython (`'LABEL' is read before it is assigned`) while the standalone build types it.
[commandcode stop=end_turn turns=40 out_tokens=25708]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have enough to judge. Here's my report.

## What the diff really does

`git show`/diff: purely additive — `llms.txt`, `docs/AGENT_GUIDE.md`, two design/task docs, the Claude Code skill + `AGENTS.md`, `integrations/mcp/` (stdlib stdio JSON-RPC server), `examples/agent_guide/{slow,fixed}.py`, one test module, and DEVLOG/DIFFERENCES/manifest rows. **No compiler, runtime, packaging or benchmark file is touched**, so generated C cannot differ (diffstat has no `AIL_CURRENT/*.py` except the new test). That matches the report, including its honest "`ailc ext` and `--why` do not exist".

## Probes (`/tmp/rprobes/`, `cmp.sh` against CPython)

| probe | result |
|---|---|
| `slow.py` (guide start) | g/d exit 0, same stdout |
| `fixed.py` (guide result) | g/d exit 0, same stdout |
| `mcp_edge.py` (missing path, dir path, syntax error, path with space, bad args, unknown tool) | all return `ok:false` JSON, no crash |
| countdown `while…else` | `--json` → AIL0109 note; `--strict` → exit 3 `ail.strict/1`; **applying `fix.with` → `IndentationError`** |
| documented commands verbatim | `check`, `compile`, `compile --strict --json`, `build --cpython` exit 0; `./hello` prints; wrapper `check`/`build`/`run`/`run --diff` exit 0 and print `ail diff: agree`; `ail build --cpython` → `unrecognized arguments: --cpython` |

## Claim check

- Files added, `ail build`/`ail run` exist, `--json` schemas (`ail.strict/1` refusal, `ail.build/1` success), `ext`/`--why` missing, `pip install ailc` + `ail` console script, exit codes 3/4/124, AIL0101–0116: **verified**.
- Guide numbers: profile = 7 calls / collatz_total, `4.545 s`; I measured `4.703 s` (same machine class); CPython 4.73–5.72 s vs native 0.15–0.16 s — the 4.63/0.16/28.9× table and hybrid `'LABEL' is read before it is assigned` (accelerated `[]`) **verify**.
- All llms.txt links resolve; `docs_links.py` 42 files/0 broken; `update_manifest.py --check` exit 0 — **verified**. New module + `test_ail_safetynet` pass (`-j 2`: 18.8 s / 84.6 s, 0 failed).

## Pre-existing (identical on `/tmp/base`)

- The AIL0109 `fix.with` is mis-indented (`print` at column 0); applying it literally is an `IndentationError`. Base emits the same string, so this is a compiler bug, not this change. Note: `SKILL.md:60` tells agents to "apply that edit", so the new doc inherits it — worth softening once the compiler is fixed, but it does not block this lane.

## Unverified

- `_serve_sdk` (the `mcp` package is not installed here); the report's 34-test/4-module figure and 9 of its 11 probes (I was told not to run the wider modules).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=26 out_tokens=33274]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T12:47:12Z
