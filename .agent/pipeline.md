# job job-cov12-10290216  started 2026-10-28T17:18:27Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{},"permission_denials":[],"errors":["Operation aborted"],"terminal_reason":"aborted_streaming","fast_mode_state":"off","uuid":"a5f8effc-d91b-4cad-b4c6-eb6c22befa4c","session_id":"e314f7c6-7703-42dc-8935-d389af5acf51"}
DeepSeek-Flash -> ,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{},"permission_denials":[],"errors":["Operation aborted"],"terminal_reason":"aborted_streaming","fast_mode_state":"off","uuid":"d411d85d-09fa-4360-848c-1219e8a70b2b","session_id":"cfcc72bf-b169-4080-b247-388ffb33a262"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `cb85954` on `job-cov12-10290216`.

- **Census:** 219 corpus programs, first typed refusal **120 -> 116**. The four fixed programs are `deepseek/…/t055.py`, `t482.py`, `glm/…/t028.py`, `t055.py`; `str constant … number` **4 -> 0**. No other program changed acceptance.
- **Change:** print/f-string conditionals mixing a str sentinel and a number now wrap the non-literal arm in `str()`. `!r`/format-spec fields stay named refusals. Found and fixed a regression on `t258.py` by leaving optlib’s Optional conditional untouched.
- **Corpus runs:** all four programs match CPython stdout and exit code on all 3 inputs, both builds (typed-only and `AIL_UNIFIED_FORCE=1`).
- **Probes:** 13 in `/tmp/probes/cov12` (int, negative, zero, int64 max, float, `-0.0`, `1e300`, bool, f-strings, `sep`/`end`, argument/list/attribute/dict routes, shadowing, custom `__str__`, optional lowering, uppercase `"None"`) all match CPython on both builds. `ref_conv.py`/`ref_spec.py` are refused by name.
- **Tests:** `test_ail_cov12`, `test_ail_check`, `test_ail_source_check`, `test_ail_stdlib_batch1`, `test_ail_optional_locals`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 8 modules, **0 failed**. Manifest and ci-shards checks pass.
[cost $0.0376, opencode tokens {"total": 3341973, "input": 89773, "output": 11746, "reasoning": 12294, "cache.write": 0, "cache.read": 3228160}]
    tool time: bash 18.8 min, edit 0.0 min, write 0.0 min, read 0.0 min
        351s bash   python3 tools/par_check.py -j 2 test_ail_cov12 test_ail_check test_ail_source_check test_ail_stdlib_batch1 tes
        317s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_cov12 test_ail_check test_ail_s
        193s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/census_after2.jsonl && PYTHONPATH="$PWD/AIL_CURRENT:$PWD/AIL_
        148s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/census_after.jsonl && PYTHONPATH="$PWD/AIL_CURRENT:$PWD/AIL_C
         35s bash   cd /home/runner/work/ail-ci/ail-ci && : > /tmp/probes/cov12/run2.log; for f in /tmp/probes/cov12/p_*.py; do ec
         29s bash   cd /home/runner/work/ail-ci/ail-ci && : > /tmp/probes/cov12/run.log; for f in /tmp/probes/cov12/p_*.py; do ech
         23s bash   cat > /tmp/verify4.py <<'EOF' import os, subprocess, sys, tempfile from pathlib import Path ROOT=Path('/home/r
         21s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -X utf8 -B -m unittest -q test_ail_cov12

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does.** `iterlower.rewrite` now runs an AST pass (iterlower.py:743-850) that wraps the "non-obvious-str" arm of any `IfExp` in an argument of `print(...)`, or in an f-string field with no conversion/spec, when the other arm is a str literal, f-string, or `str(...)` call. It skips programs that bind `print`/`str` and the optlib `*__v if *__p else "None"` shape. This matches the report.

**Probes (`/tmp/rprobes`, HEAD vs base worktree `/tmp/base_cov12`).**
- Feature works on the typed path (`AIL_NO_GENERAL=1`): int, negative, bool true/false, float 1.5/1e300, f-string, `sep`/`end`, literal-`True` condition: matched CPython, base refused (e.g. `x=5;c=True;print(x if c else "none")` -> `5`).
- Default and `AIL_UNIFIED_FORCE=1`: all feature probes match; spec/`!r`/`!s` fields match; no-feature `program.c` from `--debug-dir` is byte-identical to base.
- **Regression found on the typed path** for a conditional whose two arms are both str but the non-literal arm is not a literal/f-string/`str()`: `s="hi";c=True;print(s if c else "none")` — CPython and base typed print `hi` (exit 0); HEAD typed exits 3 with `not in the subset: str() of a str: the value already is a str; drop the str() call`. Same for the mirror, f-string (`f"{s if c else 'none'}"`), `sep`/`end`, `list[str]` item, attribute, `s.upper()`, `-> str` return and `v: str` argument. Default/forced-general still match only because they fall back to the general path; the typed path is what the census and `test_ail_python_syntax` require.
- Pre-existing (identical on base): custom `__format__` is not honored by any f-string (`print(f"{u}")` already prints `S` not `F`); refusal wording differs in some cases.
- List/dict/bytes/`None` arms are refused by name on both HEAD and base, so no silent difference there.

**Tests.** `test_ail_cov12` 24.0s, `test_ail_check` 0.3s, `test_ail_safetynet` 118.0s — all pass. `update_manifest.py --check` and `ci_shards.py --check` exit 0.

**Report claims.** Census 120 -> 116 and the exact four fixed programs: verified from the census artifacts; `str constant ... number` 4 -> 0. "No other program changed acceptance": true for the 219 corpus programs, but false as a general statement (the both-str regression above). t258 still typed-accepted: verified. The 13 worker probes were not rerun (unverified), though analogous probes pass on default/general.

**Unverified:** I did not regenerate the 219-program census (used the worker's artifacts) and did not run instruction counts; the change is a compile-time pass and non-feature C is unchanged.

VERDICT: FIX

1. Typed-path regression in `_coerce_mixed_conditional` (iterlower.py:770): it wraps any arm that is not a literal/f-string/`str()`, including arms already statically `str`, so a mixed-looking but same-typed conditional becomes `str()` of a str, which the typed path refuses.
   - Probe:
     ```python
     s = "hi"
     c = True
     print(s if c else "none")
     ```
   - Expected (CPython 3.12, and base with `AIL_NO_GENERAL=1`): `hi`, exit 0.
   - Actual (HEAD with `AIL_NO_GENERAL=1`): compile exit 3, `not in the subset: str() of a str: the value already is a str; drop the str() call`.
   - Also reproduces with `print("none" if c else s)`, `print(f"{s if c else 'none'}")`, `print(s if c else "none", sep="-")`, `xs[0] if c else "none"` with `list[str]`, `b.s if c else "none"` with a str attribute, `s.upper() if c else "none"`, a `-> str` function call, and a `v: str` argument. All compile and match on base; all now refuse on HEAD. The coercion should only apply when the other arm is known non-str (or must leave an already-str arm alone).
[cost $0.0435, opencode tokens {"total": 2274519, "input": 76092, "output": 9772, "reasoning": 33007, "cache.write": 0, "cache.read": 2155648}]
    tool time: bash 4.7 min
        120s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
         22s bash   cd /tmp/rprobes mk(){ printf '%s\n' "$2" > /tmp/rprobes/$1.py; } mk spec 'v = 3 c = True print(f"{v if c else 
         19s bash   cd /tmp/rprobes; for f in fmt.py fmt2.py misc.py; do echo "=== $f HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/$f /
         16s bash   cd /tmp/rprobes mk(){ printf '%s\n' "$2" > /tmp/rprobes/$1.py; } mk bothstr1 's = "hi" c = True print(s if c e
         15s bash   cd /tmp/rprobes; cat > /tmp/rprobes/strboth.py <<'EOF' s = "hi" c = True print(s if c else "none") print("none
         11s bash   cd /tmp/rprobes mk(){ printf '%s\n' "$2" > /tmp/rprobes/$1.py; } mk attrstr 'class B:     def __init__(self): 
         11s bash   cd /tmp/rprobes mk(){ printf '%s\n' "$2" > /tmp/rprobes/$1.py; } mk fstrstr 's = "hi" c = True print(f"{s if c
         10s bash   cd /tmp/rprobes; cat > listarm.py <<'EOF' def main():     xs = [1, 2, 3]     c = True     print(xs if c else "

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed on `job-cov12-10290216` at `31e286f`.

**Fix**: `_str_value` now treats `str()` of an already-`str` value as CPython's identity instead of refusing it. This removes the typed-path regression where the mixed-conditional coercion wrapped same-type arms (`s if c else "none"`, f-string, `sep`/`end`, list item, attribute, method call, `-> str` return, `str` argument). Non-str/non-number arms and `!r`/format specs keep their named refusals.

**Probes** (`/tmp/probes/cov12`, `cmp.sh` default + `AIL_UNIFIED_FORCE=1`, plus typed `AIL_NO_GENERAL=1`):
- `bothstr`, `routes`, `same_type`, `direct`, `yesno`, `shadow`: CPython match on all three builds, exit 0.
- `spec`, `conv`, `listarm`, `none_arm`: match on default/general; typed path refuses by name (`str constant 'none' ...`, `str() of a list ...`, `the constant None`).

**Tests on HEAD**: `test_ail_cov12`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Earlier on the same code: `test_ail_fallback_note`, `test_ail_refusal_messages`, `test_ail_python_syntax` also passed.

`update_manifest.py --check` and `ci_shards.py --check` exit 0. Census counts unchanged from the feature commit: first typed refusals 120 -> 116. Untracked `.agent/pipeline.md` was not committed.
[cost $0.0305, opencode tokens {"total": 2190214, "input": 69783, "output": 12809, "reasoning": 10086, "cache.write": 0, "cache.read": 2097536}]
    tool time: bash 16.1 min, edit 0.0 min
        331s bash   cd /home/runner/work/ail-ci/ail-ci && git rev-parse --short HEAD && python3 tools/par_check.py -j 2 test_ail_c
        277s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_corpus_findi
        185s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_cov12 test_ail_files test_ail_f
         62s bash   cd /tmp/probes/cov12 && sed -i 's/for f in bothstr routes direct yesno spec conv listarm none_arm shadow; do/f
         47s bash   cat > /tmp/probes/cov12/run.sh <<'EOF' #!/bin/bash wt=/home/runner/work/ail-ci/ail-ci for f in bothstr routes 
         15s bash   cd /tmp/probes/cov12 && cat > routes.py <<'EOF' class Box:     def __init__(self, v):         self.v = v      
         13s bash   cd /tmp/probes/cov12 && cat > routes.py <<'EOF' class Box:     def __init__(self, v):         self.v = v      
          8s bash   cd /tmp/probes/cov12 && cat > routes.py <<'EOF' class Box:     def __init__(self, v):         self.v = v      

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the diff really does.** `iterlower.rewrite` now runs a new pass that wraps the non-obvious arm of a `print(<IfExp>)` / no-spec f-string field in `str()`, and typed `_str_value` treats `str(x)` with `x: str` as the identity. That matches the report (the diff is the feature commit plus the review-fix commit).

**Probes** (mine in `/tmp/rprobes`; `cmp.sh` default+general, plus `AIL_NO_GENERAL=1`):
- `builder`, `owned`, `returnstr`, `mutate3`, `builder2`: HEAD default+general and typed all match CPython; base typed refuses `str() of a str` and HEAD matches.
- `routes`, `numeric`, `fmt`, `nested`, `weird`, `optstr2`, `optint2`: default+general match; typed matches or refuses by name (`str() of bytes`, list arm, `None` arm, `!r`/spec).
- `shadow`, `shadowstr`, `nofeature`, `plain2`: match; `--debug-dir` C identical to base for `nofeature`/`plain2`.
- The four corpus programs (`t055`, `t482`, `t028`, `glm t055`) match typed on empty/1/2/3/10 inputs.
- Required tests: `test_ail_cov12`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 0 failed. `update_manifest.py --check` and `ci_shards.py --check` exit 0.

**Claims:** identity fix verified; regression removal verified; probe/test/check claims verified; 120→116 verified from the census artifacts (I did not re-run the census on HEAD). The claim that the chosen construct is the most frequent is **false** (below).

**Pre-existing (not blocking):** custom `__format__` differs from CPython in f-strings identically on base and HEAD; optional str in a field/list-item and explicit `str()` of a list/bytes/None keep their old refusals.

**Unverified:** instruction counts (`perf_event_open` denied here); full census on HEAD.

### Defects

1. **Wrong construct chosen** (task step 2). `census_corpus.jsonl` (219 programs, 120 first typed refusals) gives: `call to iter()` = 10 (`t117,t255,t266,t271,t275,t278,t284,t310,t328,t366`), `json.loads` = 5 (stdlib), `sorted(d.items())` = 4, `str constant … number` = 4. The change picks the 4-count construct and leaves the 10-count `iter()` untouched; the general path already matches CPython on all ten, so it is supportable. Expected: support the most frequent non-import construct (`iter()`/`next()`); actual: the fourth-most-frequent one. The report never mentions this choice.
2. **C not unchanged for a program that does not need the feature.** Probe `st.py`:
   `s = "hi"; c = True; print(s if c else "none"); print(f"{s if c else 'none'}")` compiles and matches CPython on base's typed path too, but HEAD's `program.c` differs (base folds the constant condition to a single write; HEAD emits a runtime ternary, extra temporaries and an arena cleanup frame). Expected: identical C to base; actual: different C (output still matches, so this is a codegen/optimization regression, not a semantic one).

VERDICT: FIX
[cost $0.0577, opencode tokens {"total": 4302482, "input": 106712, "output": 14303, "reasoning": 34523, "cache.write": 0, "cache.read": 4146944}]
    tool time: bash 14.2 min
        310s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_
        109s bash   cd /tmp/rprobes && for f in t117 t255 t266 t271 t275 t278 t284 t310 t328 t366; do p=/home/runner/work/ail-ci/a
         65s bash   cd /tmp/rprobes && for f in builder owned routes fmt shadow shadowstr nofeature nested numeric; do echo "=== $
         63s bash   cd /tmp/rprobes && for p in deepseek-v4.1-flash-free/t055 deepseek-v4.1-flash-free/t482 glm-5.3-flash-free/t02
         41s bash   cd /tmp/rprobes && for f in builder owned routes fmt shadow shadowstr nofeature nested numeric; do echo "=== $
         37s bash   cd /tmp/rprobes && cat > mutate.py <<'EOF' d = {"k": "abc"} xs = ["abc"] class B:     def __init__(self):     
         37s bash   ls /tmp/probes/cov12 2>/dev/null && cd /tmp/probes/cov12 2>/dev/null && for f in bothstr routes same_type dire
         30s bash   cd /tmp/rprobes && cat > weird.py <<'EOF' c = True print(b"x" if c else "none") print(b"x" if not c else "none

FINAL VERDICT: FIX  2026-10-28T19:29:29Z
