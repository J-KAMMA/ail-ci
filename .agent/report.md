# job job-pre327-10271919  started 2026-10-27T10:19:40Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"4e76fc1f-bb2c-44dd-a82e-2f3f0610787a","session_id":"a891288d-5013-4072-a9ed-7a404a0cc07e"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"9ce348cd-8009-46cf-a7fd-c56c5d23b11a","session_id":"0a76d394-0f3f-4a01-8d55-93f80c7f3c8c"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

Reproduced the pre323 items on this tree:
- Direct out-of-int64 literal (incl. slice bound) was already refused by name (`int64 literal out of range`).
- User-class slices through a parameter, `for`/`with` target, or tuple-unpacked item built, then failed at run time on both builds with `NotImplementedError: slicing an instance through __getitem__ is not supported`.

**Fix:** the general path's unknown-kind slice branch now requests its slice prelude before emitting, then passes a real slice object to `__getitem__`. Commit `4181a8e`.

**Probes** in `/tmp/probes/pre327`, both builds:
- Refused by name: `p1_literal`, `p19_huge`, `p20_huge_neg`.
- Match CPython: `p2_for_inrange`–`p15_assign`, `p17_incode`, `p18_nofeature` (routes, empty/negative/None/bool bounds, built-ins, inherited types, assignment/deletion, slice fields).
- Pre-existing only: `p16_other` / `p16b_other_only` still say `'instance' object is not subscriptable` where CPython names `'A'`; identical on the base.

**Tests on final commit:** `test_ail_pre327`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (300s). `update_manifest.py --check` passes. No speed check: compiler-only change, no hot code.
[cost $0.0000, opencode tokens {"total": 5828548, "input": 105441, "output": 14377, "reasoning": 19130, "cache.write": 0, "cache.read": 5689600}]
    tool time: bash 8.6 min
        302s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         48s bash   cd /tmp/probes/pre327 && cat > p11_routes.py <<'EOF' class C:     def __init__(self, n):         self.items = 
         47s bash   for f in p1_literal p2_for_inrange p3_with p4_tuple p5_direct p6_assign p7_arg p8_if p9_set_for p10_del_for; d
         40s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre3
         19s bash   cd /tmp/probes/pre327 && cat > p5_direct.py <<'EOF' class C:     def __getitem__(self, i):         return (i.s
         14s bash   for f in p1_literal p2_for_inrange p3_with p4_tuple; do echo "===== $f"; bash ~/tools/cmp.sh /tmp/probes/pre32
         11s bash   cd /tmp/probes/pre327 && cat > p11_routes.py <<'EOF' class C:     def __init__(self, n):         self.items = 
         11s bash   cd /tmp/probes/pre327 && cat > p9_set_for.py <<'EOF' class C:     def __init__(self):         self.items = [1,

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre327 (`4181a8e`)

**What the change really does:** in `boxclosure`'s unknown-kind slice branch (`pyboxed2.py:5630`), it now raises `NeedSlice` when the slice prelude is absent, so a class instance reached through an unknown value gets the prelude and a real slice object, instead of falling through to `ail_op_getslice`. This matches the report.

**Defect found — slice bounds are evaluated twice when the receiver is an instance.** `_slice_bounds` evaluates the non-`None` bounds before the tag test, then the instance arm calls `_slice_obj`, which evaluates them again.

```python
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)

def f(): print("f-called"); return 1
def g(): print("g-called"); return 4
def h(): print("h-called"); return 2

def cut(x):
    return x[f():g():h()]

print(cut(C()))
```

CPython: `f-called / g-called / h-called / (1, 4, 2)`
HEAD (both builds): `f-called / g-called / h-called / f-called / g-called / h-called / (1, 4, 2)`

Same root cause with mutating bounds (`x[data.pop():data.pop()]`): CPython prints `(2, 1, None)` and `[0]`; HEAD exits 1 with `IndexError: pop from empty list`. Base refuses with the old `NotImplementedError`, so this wrong-output path is new for the route the task asked to fix.

**Other probes (HEAD vs base):** built-in slices with a class defining `__getitem__` (list/tuple/str/bytes/bytearray/range) match CPython; non-instance bound side effects run once; int64 literal refusal; no-feature C is byte-identical to base (`--debug-dir`, unified). `test_ail_pre327` + `test_ail_safetynet`: 2 modules, 0 failed. `update_manifest.py --check`: pass.

**Claims:** diff summary verified; int64-literal refusal verified; pre-existing `dict` KeyError→TypeError verified (same on base, see below); the DEVLOG claim that built-in-only slices now generate different C was not reproduced (C identical on my program); 4-module test run unverified (only the 2 review-scope modules run).

**Pre-existing (not blocking):** `{"a":1}[1:2]` gives `TypeError` on both HEAD and base where CPython gives `KeyError`. `p16` instance-name difference not re-run.

**Unverified:** `test_ail_files` / `test_ail_corpus_findings3`; the worker's `/tmp/probes/pre327` set beyond the cases above; speed (compiler-only).

VERDICT: FIX

1. Double evaluation of slice bounds for an instance reached through an unknown value. Probe `p_double.py` above: expected `f-called g-called h-called (1, 4, 2)` once each, actual each printed twice (and `p_pop.py` expected `(2, 1, None)` / `[0]`, actual `IndexError: pop from empty list`). Cause: `_slice_bounds` runs before the `AIL_T_INST` test and `_slice_obj` runs the same bounds again in the instance arm (`AIL_CURRENT/python/pkg-v12/pyboxed2.py:5634-5640`).
[cost $0.0000, opencode tokens {"total": 572896, "input": 30858, "output": 4712, "reasoning": 8814, "cache.write": 0, "cache.read": 528512}]
    tool time: bash 3.6 min
        111s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
         32s bash   cd /tmp/rprobes && for f in p_double p_builtin_with_class p_effects_noninst p_types; do echo "===== $f"; bash 
         31s bash   cd /tmp/rprobes && for f in p_double p_builtin_with_class p_effects_noninst p_types; do echo "===== BASE $f"; 
         11s bash   cd /tmp/rprobes && rm -rf dbg_head dbg_base exe_h exe_b && AIL_UNIFIED_FORCE=1 AIL_NO_CACHE=1 AIL_QUIET_FALLBA
         11s bash   cd /tmp/rprobes && rm -rf dbg_head dbg_base && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /home/runner/work/a
          9s bash   cd /tmp/rprobes && cat > p_pop.py <<'EOF' class C:     def __getitem__(self, i):         return (i.start, i.st
          8s bash   cd /tmp/rprobes && cat > p_ownslice.py <<'EOF' class C:     def __getitem__(self, i):         return i  slice 
          4s bash   cd /tmp/rprobes && cat > p_nofeature.py <<'EOF' class C:     def __getitem__(self, i):         return i  print

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the double evaluation: `_slice_bounds` now emits only in the non-instance arm, so instance bounds run once.

Probes (`/tmp/probes/pre327fix`, both builds via `cmp.sh`):
- `p_eval_once` — match CPython
- `p_mutating` — match CPython (`(2, 1, None)`/list results, no IndexError)
- `p_types` — match CPython (empty/negative/None/bool/step; list/tuple/str/bytes/bytearray/range)
- `p_routes` — match CPython (arg, alias, attribute, dict, list item, for, with, unpack)
- `p_literal_bounds` — refused by name: `int64 literal out of range`

Tests on final source: `test_ail_pre327`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` passes. Committed as `2e4cd94`.
[cost $0.0000, opencode tokens {"total": 530421, "input": 27497, "output": 4447, "reasoning": 3885, "cache.write": 0, "cache.read": 494592}]
    tool time: bash 4.6 min, edit 0.0 min
        246s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         28s bash   cd /tmp/probes/pre327fix && for f in p_eval_once p_mutating p_types p_routes p_literal_bounds; do echo "===== 
          0s bash   cd /tmp/probes/pre327fix && for f in p_eval_once p_mutating p_types p_routes p_literal_bounds; do echo "===== 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' from pathlib import Path p=Path('DIFFERENCES.md') s=p.
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/python/pkg-v12/pyboxed2.py
          0s bash   git status && git log --oneline -5 && pwd

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Review of `work..HEAD` (2 commits) in `/home/runner/work/ail-ci/ail-ci` (run 11:05–11:17 UTC).

**What the diff really does.** In the general path's unknown-kind `expr_Subscript` slice branch it (a) drops the `want_slice` pre-gate and raises `NeedSlice` instead, so an instance reached from an unknown value gets a real slice object, and (b) moves `_slice_bounds` into the non-instance `else` arm, so an instance no longer evaluates its bounds twice (once for `_slice_bounds`, once in `_slice_obj`). Plus `test_ail_pre327.py`, manifest/check/shards/DEVLOG/DIFFERENCES. This matches the report.

**Claims**
- Double evaluation fixed, bounds run once — verified (`p2_eval_once`, `p3_mutating`, worker `p_eval_once`/`p_mutating`: `f/g/h` once each; `data.pop()` result `(2, 1, None)`).
- Unknown-kind instance slicing now matches CPython — verified (`p1_repro`, `p3_mutating`, `p26_mutate_receiver_container`, `p22` inheritance via `B/D`); base fails `NotImplementedError` on the same probes.
- Routes arg/alias/attribute/dict/list item/for/with/unpack — verified (`p1_repro`, worker `p_routes`).
- Types/empty/negative/None/bool/step/bytes/bytearray/range — verified (`p7_types`, `p9_extra`, worker `p_types`).
- `2**63` bound refused by name — verified (`p15_huge`: `int64 constant out of range`, both builds/base).
- Tests pass — `test_ail_pre327` + `test_ail_safetynet` re-run on HEAD: 2 modules, 0 failed (115 s). `update_manifest.py --check` rc=0.
- C unchanged when no class defines `__getitem__` (`p12_noclass`) and when no slice is used (`p5_no_feature`) — verified identical C. A built-in-only slice plus a class defining `__getitem__` (`p11_builtin_only`) does add the 119-line SLICE prelude and the tag test; output matches CPython. The report discloses this.

**Pre-existing (not blocking)**
- `p20`/`p23` (a function whose parameter/local is named `slice`, then an instance slice): HEAD raises `TypeError: 'int' object is not callable`. Same root cause exists on base — `p23` (known-instance form) fails identically on base and HEAD — because `_slice_obj` constructs a `slice(...)` call from the user-visible name. Base's unknown-kind form failed with `NotImplementedError`, so no previously-correct program regresses.
- `p10`/`p24`/`p25` (`dict` with a slice key): CPython 3.12 gives `KeyError slice(...)`, AIL `TypeError 'dict' object is not subscriptable`; `p25` is identical on base.
- Multiple inheritance (`p22`) refused by name on both.

**Unverified / skipped.** `test_ail_files`, `test_ail_corpus_findings3` not re-run (out of review scope). No speed check: no `~/corpus/gdev` program defines `__getitem__` (grep empty), so the changed branch is unreachable there.

VERDICT: ACCEPT
[cost $0.0477, opencode tokens {"total": 2009182, "input": 94635, "output": 10353, "reasoning": 36162, "cache.write": 0, "cache.read": 1868032}]
    tool time: bash 6.4 min, write 0.0 min
        117s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         47s bash   cd /tmp/rprobes && for f in p1_repro p2_eval_once p3_mutating p4_slice_name p5_no_feature p6_noninst p7_types 
         29s bash   cd /tmp/probes/pre327fix && for f in p_eval_once p_mutating p_types p_routes p_literal_bounds; do echo "===== 
         27s bash   cd /tmp/rprobes && for f in p13_local_slice p14_shadow_top p15_huge p16_lambda_slice; do echo "===== $f HEAD =
         23s bash   cd /tmp/rprobes && for f in p1_repro p2_eval_once p3_mutating p9_extra p10_dict_int; do echo "===== $f BASE ==
         20s bash   cd /tmp/rprobes && for f in p24_slice_key p25_dict_slice_explicit; do echo "===== $f HEAD ====="; bash ~/tools
         17s bash   cd /tmp/rprobes && for f in p18_local_builtin p19_local_inst; do echo "===== $f HEAD ====="; bash ~/tools/cmp.
         17s bash   cd /tmp/rprobes && for f in p1_repro p9_extra p10_dict_int; do echo "===== $f HEAD ====="; bash ~/tools/cmp.sh

## full suite
test_ail_silent5

## worker report (suite fix)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed.

`test_ail_silent5` failed because its assertion still expected an instance slice reached through an unknown value to raise `NotImplementedError`. The accepted fix now correctly passes a slice object to `__getitem__`, matching CPython (`[1]`). Updated the stale test/docstring expectation.

Verified:
- `test_ail_silent5`: 21 tests OK
- `test_ail_pre327`: 1 test OK

Commit: `7c9fc7b`
[cost $0.0053, opencode tokens {"total": 172308, "input": 17321, "output": 1892, "reasoning": 1799, "cache.write": 0, "cache.read": 151296}]
    tool time: bash 2.5 min, edit 0.0 min, read 0.0 min
         82s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_silent5 2>&1 | tail -60
         41s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre327 2>&1 | tail -20
         27s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_silent5 2>&1 | tail -20
          0s bash   pwd && ls -la && git status && git log --oneline -10
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_silent5.py && git commit -m "pre327: update
          0s bash   git show --stat HEAD && git show --stat HEAD~1
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && git diff --stat && git diff -- AIL_CURRENT/test_ai
          0s bash   git show HEAD -- AIL_CURRENT/python/pkg-v12/pyboxed2.py AIL_CURRENT/test_ail_pre327.py

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T12:35:24Z
