# job job-rbobs4-11092249  started 2026-11-09T13:55:36Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Re-application complete and committed as `1fa4e18f`.

**What I did**
- Fetched `job-obs4-op1109`. The tree already contained obs1–obs3 (`ail_cpython_hybrid.py`, tests and design doc were byte-identical to `622160b4`), so I applied the missing obs4 delta; no conflicts occurred.
- Files: `ail_cpython_hybrid.py` (+951/−67), new `test_ail_hybrid_calls.py` (326 lines) and `test_ail_hybrid_methods.py` (300), `test_ail_hybrid_lists.py` (5), 2 `tests.d` registrations, `docs/design/OBSERVED_TYPES.md` (+161), `lab/wedge/observe_probe.py`, new `obs4_task{2,3}.json`.
- `tools/diff_ids.py` does not exist on this tree (exit 2). `tools/update_manifest.py` regenerated shards `3e/4c/c4/d2/ec`; `--check` passes.
- Added an `AIL_CURRENT/DEVLOG.md` entry at the top. No new `DIFFERENCES.md` row (the change adds none).

**Probes** (`/tmp/probes`, run with `bash ~/tools/cmp.sh <p> $PWD`)
| probe | general g | default d | hybrid `build --cpython` | native accelerated |
|---|---|---|---|---|
| `p_consts.py` (constants, retyping, huge int, pre-assignment NameError) | same | same | same | 2 |
| `p_calls.py` (native→native, bool/negative, recursion) | same | same | same | 6 |
| `p_methods.py` (read-only methods, empty, negative index, field retype, subclasses) | same | same | same | 5 |
| `p_edges.py` (empty/non-ASCII/NUL strings, list fields, attribute, dict value, missing key) | same | same | same | 1 |

All four match CPython stdout and exit on both `cmp.sh` builds and on the hybrid run. I simplified the general-path probes to the AIL subset (dropping runtime callee rebinding and dynamic `__class__` assignment, which the general path handles differently and which the hybrid test modules cover).

**Tests** on the final code, `-j 2`: `test_ail_hybrid_calls`, `test_ail_hybrid_methods`, `test_ail_hybrid_lists`, `test_ail_cpython_hybrid`, `test_ail_observe`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 8 modules, 0 failed (352s). The hybrid tests include the recursion-limit boundaries (`depth124`/`deep124` classify as `RecursionError`), so those were verified by test rather than by my probes.

Working tree is clean except the pre-existing untracked `.agent/pipeline.md`.
[commandcode stop=end_turn turns=49 out_tokens=37918]

## review 0 failed to run:     [denied near] {"type":"event","event":{"type":"tool_queued","toolCallId":"call_00_l30f9rmh0lkb0s6469uoyufs","toolName":"shell_command","input":{"command":"mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > r_consts.py <<'EOF'\nLIMIT = 3\nSCALE = 2.5\nSEP = \",\"\nNEG = -0.0\nTENTH = 0.1\nBIG = 9223372036854775807\     [denied near] {"type":"event","event":{"type":"tool_denied","toolCallId":"call_00_l30f9rmh0lkb0s6469uoyufs","toolName":"shell_command"}}     [denied near] {"type":"event","event":{"type":"run_end","result":{"finalText":"Let me see how the hybrid runner is invoked and what the tests cover, then write probes.","stopReason":"permission_denied","turnCount":14,"usage":{"inputTokens":366429,"outputTokens":8544,"cacheReadTokens":334848,"cacheWriteTokens":0}, 

## review 0
[model commandcode/deepseek-v4.1-flash]
I'll create the probe programs and a hybrid-path harness.
[commandcode stop=permission_denied turns=10 out_tokens=11339]
    [denied near] {"type":"event","event":{"type":"tool_queued","toolCallId":"call_00_hcbq7cnpvk5ff11voi6m0ukq","toolName":"shell_command","input":{"command":"mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > p1_consts.py <<'EOF'\nLIMIT = 3\nLOW = -9223372036854775808\nHIGH = 9223372036854775807\nF = 2.5\nS = \"東,x\"
    [denied near] {"type":"event","event":{"type":"tool_denied","toolCallId":"call_00_hcbq7cnpvk5ff11voi6m0ukq","toolName":"shell_command"}}
    [denied near] {"type":"event","event":{"type":"run_end","result":{"finalText":"I'll create the probe programs and a hybrid-path harness.","stopReason":"permission_denied","turnCount":10,"usage":{"inputTokens":275924,"outputTokens":11339,"cacheReadTokens":243840,"cacheWriteTokens":0},"systemPromptTokens":null,"nex

FINAL VERDICT: ERROR  2026-11-09T14:13:51Z
