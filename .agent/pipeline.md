# job job-pre388-10280828  started 2026-10-27T23:34:19Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> ice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"8458027d-17ad-4286-b99d-48893d09e90d","context_usage_ratio":0.019625},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.16193914417142855}},"permission_denials":[],"fast_mode_state":"off","uuid":"8de0ed19-abe7-4e14-888a-fb93a24fc202","session_id":"cbc685f3-5d69-447e-be5f-33a0669bc2bc"}

## worker report 0
[model qoder/DeepSeek-Flash]
**Fixed the first recorded difference (r05) on branch `job-pre388-10280828`, commit `c2969a3`.**

**Cause:** `_escaped_constant_names` built one scope-wide "may mutate" set, so a later `a[0] = 1.5` made the flat list dynamic and `x = a[0]` stayed unknown at `int(x)`. The analysis now returns escape events per top-level statement (`_escaped_constant_statements`), and `_scope_constant_map` walks statements in order: a scalar read through a load-only subscript keeps the literal value up to the mutating statement. Top-level statements run once in order, and uses inside nested definitions count at the definition statement, so a mutation that comes first still matches CPython.

**Result:** r05 is refused by name on both builds (`int() of a float outside int64: 1e+300 (CPython makes a big integer)`), as are 13 more variants (direct read, dict value, computed index, `del`, alias chain, tuple, negative, 2^63 float, function-local, call/`print` between, int/str item). r10 (attribute-held list) still traps on both builds; it is the review's second item, recorded as `C?-job-pre388-10280828-2` (open).

**Probes** (`/tmp/probes/pre388`, both builds, `bash ~/tools/cmp.sh`):
- `v01`–`v12`, `w01`–`w15`, `x01`–`x06`, plus `pre388_r05`, `pre388_r10`.
- All match CPython or are refused by name except the pre-existing routes: `v11`/r10 (attribute-held list), `w02`/`w03` (list/float via a function argument), `w04` (attribute-held scalar) — recorded in DIFFERENCES.

**Tests on the final commit:** `test_ail_pre388` (new, 2 tests / 24 programs), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 27 tests, OK (1 skipped). Earlier regression run of `test_ail_pre322/311/31/9/39/357/358/359`: 17 tests OK. `update_manifest.py --check` exits 0; DEVLOG and DIFFERENCES updated.

## review 0
[model qoder/DeepSeek-Flash]
All checks are done. Here is the review report.

---

## Review: job-pre388-10280828, commit `c2969a3`

**What the change really does (one line):** replaces the scope-wide "escaped container" set used by the `int()` int64 diagnostic fold with per-top-level-statement escape events (`_escaped_constant_statements`), so `_scope_constant_map` folds a scalar read through a load-only subscript until the statement that first mutates the container, and drops containers from that statement on. Checker-only: it adds no codegen, runtime, I/O or buffer changes.

**Probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh`, g and d builds, HEAD vs `/tmp/base`):

| probe | case | HEAD |
|---|---|---|
| p01_r05 | recorded alias read then mutate | refused by name both builds (base: run-time `integer overflow`) — fix works |
| p02, p09 | scalar read then `global x` rebind in nested fn (list, dict) | same stdout (guard: `declared`=Global/Nonlocal names) |
| p04 | `nonlocal x` rebind | same stdout |
| p03, p22 | class-body `global`, `__setitem__` | pre-existing "not in the subset" refusal, identical on base |
| p05 | attribute-held list (r10) | run-time trap, identical on base — pre-existing |
| p06 | list via function argument | run-time trap, identical on base — pre-existing |
| p20 | scalar via instance attribute | run-time trap, identical on base — pre-existing (w04) |
| p07, p11, p12 | mutation first, through simple/multi-target/unpacked alias | same stdout |
| p08, p10, p26 | read, then mutation in empty loop / slice store / iteration | refused correctly (CPython big int) |
| p13, p25 | scalar rebound by walrus / `for` target | same stdout (`stores != 1` blocks the fold) |
| p16, p17 | `match` capture / `with … as` rebind | same stdout (`python_surface` lowers captures to Stores) |
| p18, p19 | scalar carried through a list item / dict value | refused correctly (base trapped: new correct refusal) |
| p14, p21, p23, p24 | unrelated; slice-first; dead `int(1e300)`; in-range via nested fn | same stdout; p23 refused identically on base (pre-existing static policy) |

**C unchanged:** `program.c` byte-identical (same sha256) between HEAD and base for p07/p14/p20 on both g and d builds; `native_report.json` differs only in temp paths. No runtime/hot-code change, so instruction counts are unchanged (icount not run).

**Tests:** `par_check.py -j 2 test_ail_pre388 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4 modules, 0 failed. `tools/update_manifest.py --check` → exit 0. Commit date and DEVLOG date agree (2026-10-27); trailer present.

**Claims:** cause, per-statement events, ordered walk, nested-def-at-definition-statement, r05 refused on both builds, 14 refused + 10 match cases (24 programs), r10 still traps, w02/w03/w04 pre-existing, test/manifest results — all **verified**. Earlier regression run of test_ail_pre322/etc. (17 tests) — **unverified** (not re-run). Worker's `/tmp/probes/pre388` — **unverified** (not in the tree).

**Pre-existing (do not block):** r10 attribute-held list; list/float through a function argument; attribute-held scalar; class-body/`__setitem__` subset refusals; uncalled `int(1e300)` static refusal; missed refusals after an earlier mutation or through a nested definition (both builds trap).

**Defects:** none found. The stale-scalar risk (a folded scalar later rebound without a counted Store) is closed by `declared` (any Global/Nonlocal in the scope subtree) and by `stores == 1`; the new folds only occur before the first detected escape, and statement ordering is conservative for nested definitions, class bodies and comprehensions.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T01:28:40Z
