# job job-pre171-10250443  started 2026-10-24T19:44:10Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":436,"duration_api_ms":309,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":444,"duration_api_ms":319,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `2372564` on `job-pre171-10250443`.

**Fix**
- `pymix` now detects trap-capable functions used indirectly: referenced as values, called inside lambdas, or reached through indirect callers/wrappers. Those candidates are rejected in favor of the general/boxed path, so the caller’s `try` remains active.
- Typed `ck_shl`/`ck_shr` guards now raise CPython’s `ValueError: negative shift count` via `adopt`.
- Added `AIL_CURRENT/test_ail_pre171.py` and registered it in `ail_check.MODULES`.
- Updated `DEVLOG.md`, `DIFFERENCES.md` (`C?-job-pre171-10250443-1`), and `MANIFEST.json`.

**Probes — all match CPython on both builds after the fix**
- `lambda_calls_helper.py`, `function_list_calls_helper.py`, `lambda_calls_helper_direct.py`, `direct_negshift.py`, `uncaught_shift_direct.py`
- `indirect_shift_left.py`, `indirect_shift_right.py`, `indirect_shift_aug.py`
- `indirect_shift_alias.py`, `indirect_shift_wrapper.py`, `indirect_shift_callback.py`
- `indirect_shift_valid.py`, `indirect_shift_uncaught.py`, `indirect_shift_empty.py`, `indirect_raise.py`

`lambda_calls_helper.py` before: `d` exited 1 and lost lines 2–4. After: both builds match CPython, including caught message and continuation. The separate int64 shift-overflow probes (`shift_overflow.py`, `lambda_calls_helper_overflow.py`, etc.) still differ; that remains the second, unfixed pre-existing difference.

**Tests on final code**
- `test_ail_pre171.py` — pass, 16.3 s
- `test_ail_safetynet.py` — pass, 102.8 s
- `test_ail_files.py` — pass, 99.9 s
- `test_ail_corpus_findings3.py` — pass, 159.9 s
- 4 modules in 203 s, 0 failed
- Also `test_ail_mixed_bounds.py` and `test_ail_flush_exit.py` passed.

Not pushed.
[cost $0.0000, opencode tokens {"total": 6016523, "input": 302725, "output": 31510, "reasoning": 23792, "cache.write": 0, "cache.read": 5658496}]
    tool time: bash 13.8 min
        259s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet.py test_ail_files.py test_ail_corpus_f
        204s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre171.py test_ail_safetynet.py test_ail_files.p
        121s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_mixed_bounds.py test_ail_flush_exit.py 2>&1 | ta
         31s bash   cat > /tmp/probes/indirect_shift_left.py <<'EOF' class Box:     def __init__(self, n):         self.n = n   de
         24s bash   for p in /tmp/probes/lambda_list1.py /tmp/probes/lambda_list2.py /tmp/probes/lambda_list3.py /tmp/probes/lambd
         23s bash   grep -rn "test_ail_pre\|pre109\|pre85" /home/runner 2>/dev/null | head -50
         20s bash   cat > /tmp/probes/lambda_neg_literal.py <<'EOF' def main():     fns = [lambda n: 1 << n, lambda n: 8 >> n]    
         19s bash   cat > /tmp/probes/lambda_calls_helper.py <<'EOF' def shift(a, b):     return a << b   def main():     fns = [l

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the change really does.** `pymix` now marks function names loaded as values, called inside a `lambda`, or reached through such callers as indirect, and rejects any trap-capable candidate among them so the caller keeps the boxed path; it also treats shifts with non-literal counts as `ValueError` traps and gives `ck_shl`/`ck_shr` CPython's `negative shift count` text via `ail_raise_value_adopt`. This matches the report.

**Probes (HEAD vs base, `bash ~/tools/cmp.sh`)**
- `p1_indirect_list.py`, `p2_indirect_callback.py`, `p3_indirect_raise.py`, `p9_global_dict.py`, `p10_map.py`, `p11_local_alias_call.py`: HEAD both builds match CPython. Base default fails the lambda/list, callback, explicit-raise and `map` cases (escaped handler / empty message), confirming the intended fix.
- `p4_shift_direct.py`: HEAD both builds match CPython (`<<`, `>>`, `<<=`, `>>=`, arg counts, message and args). Base default had the empty message.
- `p5_no_feature.py`: generated C identical base vs HEAD on both builds.
- `p6_const_shift.py`: only the `ck_shr` helper text differs (the intended message change); no logic churn.
- `p8_generator.py`: both base and HEAD exit 1 without catching — pre-existing, not fixed.
- `p7_overflow.py`: `1 << 63`/`1 << 64` differ identically on base and HEAD — the acknowledged second pre-existing difference.

**Tests.** `test_ail_pre171.py` ok 16.3 s, `test_ail_safetynet.py` ok 101.8 s, 2 modules 0 failed. `tools/update_manifest.py --check` passes. `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_mixed_bounds`, `test_ail_flush_exit` not re-run (unverified).

**Report claims**
- Indirect rejection, shift message, test registration, records: verified.
- "All probes match CPython": verified for my probes; the worker's exact probe list was not re-run.
- "int64 overflow remains separate": verified.
- "No speed regression": unverified (perf denied); `pymix` candidate sets are unchanged for the 18 gdev programs containing shifts, which supports no shift-corpus change.
- Not pushed: not checked.

**Pre-existing (not blocking).** Deferred generator-expression dispatch (`p8_generator.py`) still escapes the caller's `try` on both builds. int64 shift overflow above 63 bits (`p7_overflow.py`) differs identically on both.

**Defect.** The switch from `ail_raise_named` to `ail_raise_value_adopt` in `ck_shl`/`ck_shr` breaks `parallel for`: `_PARALLEL_DIE_EDITS` intercepts only `ail_die`/`ail_raise_named`, so a worker-thread negative shift longjmps across threads. The generated C for the probe below differs from base only in that branch.

Probe `/tmp/rprobes/par/heavy.ail` (built directly, `AIL_THREADS=4`):
```ail
fn work(n: int, b: int) -> int {
    let xs: list[int] = [0] * n;
    parallel for i in range(0, n) {
        let t = i;
        for k in range(0, 200) { t = (t * 1103515245 + 12345) % 2147483647; }
        if i == n - 1 { xs[i] = t << b; } else { xs[i] = t; }
    }
    return xs[5];
}
fn main() {
    try { print(work(100000, -1)); }
    except ValueError as e { print("caught", e.kind); }
    print("done");
}
```
Expected (base): `caught ValueError` / `done`, exit 0. Actual (HEAD): Segmentation fault, exit 139; `AIL_THREADS=1` on HEAD prints the expected lines. Fix by routing this trap through the parallel interception (`ail_raise_msg`/`ail_raise_named`-style) or extending the interception to `ail_raise_value_adopt`.

VERDICT: FIX
1. `parallel for` with a negative shift segfaults on HEAD but is caught correctly on base; probe `/tmp/rprobes/par/heavy.ail`, expected `caught ValueError`/`done` exit 0, actual segfault exit 139.
[cost $0.0000, opencode tokens {"total": 2236976, "input": 166889, "output": 8641, "reasoning": 19718, "cache.write": 0, "cache.read": 2041728}]
    tool time: bash 3.5 min
        103s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         28s bash   cd /tmp/rprobes && for p in p1_indirect_list p2_indirect_callback p3_indirect_raise p4_shift_direct p5_no_feat
         20s bash   cd /tmp/rprobes && for p in p1_indirect_list p2_indirect_callback p3_indirect_raise p4_shift_direct p5_no_feat
         17s bash   cat > /tmp/rprobes/p8_generator.py <<'EOF' def shift(a, b):     return a << b  def main():     gen = (shift(1,
         15s bash   cd /tmp/rprobes && cat > p6_const_shift.py <<'EOF' def f(x):     return x << 3  def main():     print(f(5), 8 
          9s bash   cd /home/runner/work/ail-ci/ail-ci && files=$(grep -rlE '<<|>>' ~/corpus/gdev/*.py | head -20); echo "$files" 
          5s bash   cat > /tmp/rprobes/p7_overflow.py <<'EOF' print(1 << 63) print(1 << 64) print("done") EOF cd /tmp/rprobes && f
          5s bash   cat > /tmp/rprobes/p11_local_alias_call.py <<'EOF' def inner(a, b):     return a << b  def outer(a, b):     g 

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `f5736a6` on `job-pre171-10250443`.

- **Fix:** worker traps via `ail_raise_value_adopt` now record code/message and unwind inside the worker; the join re-raises on the caller. No cross-thread longjmp, no leak.
- **Parallel probes:** review `heavy.ail` and `par2_ops.ail` (`<<`, `>>`, `<<=`, `>>=`, negative + valid, argument counts) match CPython at `AIL_THREADS=1/2/4/8`; uncaught probe matches stdout, stderr (`ValueError: negative shift count`) and exit 1. The general build cannot compile `parallel for` at all — it refuses identically on base.
- **Other probes:** 19/20 `cmp.sh` probes match CPython on both builds; only `shift_overflow.py` differs, the acknowledged unchanged int64 `1<<63` / `1<<64` difference.
- **Tests (final commit):** `test_ail_pre171` 18.0 s, `test_ail_safetynet` 103.1 s, `test_ail_files` 100.6 s, `test_ail_corpus_findings3` 160.6 s, `test_ail_parallel_for` 14.5 s — 5 modules, 0 failed. `update_manifest.py --check` passes. Not pushed.
[cost $0.0508, opencode tokens {"total": 3803069, "input": 129061, "output": 12637, "reasoning": 21563, "cache.write": 0, "cache.read": 3639808}]
    tool time: bash 6.6 min
        205s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre171 test_ail_sa
         67s bash   ls /home/runner/work/ail-ci/tools 2>&1 | head; sed -i 's#$wt/../tools/cmp.sh#/home/runner/tools/cmp.sh#' /tmp/
         67s bash   bash /tmp/probes/run_cmp_loop.sh > /tmp/probes/cmp_final.log 2>&1; echo rc=$?; grep -E '^(ok|PROBLEM)' /tmp/pr
         18s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 600 python3 -X utf8 -B -m unittest -q
          6s bash   cd /tmp/probes && python3 - <<'EOF' import pathlib a=pathlib.Path('par2_sources.ail') t=a.read_text() t=t.repl
          5s bash   cat > /tmp/probes/run_par2.sh <<'EOF' #!/bin/bash wt=/home/runner/work/ail-ci/ail-ci set -u fail=0 for base in
          5s bash   cat > /tmp/probes/par2_sources.ail <<'EOF' fn work(n: int, arg: int, xs: list[int], d: dict[str, int], mode: i
          4s bash   cat > /tmp/probes/par2_sources.ail <<'EOF' struct Box { b: int; } fn work(n: int, b: int) -> int {     let out

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report — `job-pre171-10250443`

**What the change really does:** `pymix` now rejects a trap-capable typed candidate when its name is used as a value, called inside a `lambda`, or reached transitively through such a call; `ck_shl`/`ck_shr` raise an adopted `ValueError("negative shift count")`; the parallel runtime traps adopted exceptions inside the worker and re-raises on the join. This matches the report.

**Probes** (`bash ~/tools/cmp.sh`, both builds, HEAD unless noted):

| probe | result |
|---|---|
| q1 lambda + list shift (original repro) | HEAD **same as CPython**; base default differs (`ValueError`, stops) → fix works |
| q2 callback / dict / attribute / alias shift | same |
| q3 `<<`, `>>`, `<<=`, `>>=`, counts −1/0/2/6 | same |
| q4 direct call under `try` + augmented | same |
| q5 no-shift program | same; `program.c`/`program_mix0.c` byte-identical to base (only tmp paths in JSON differ) |
| q8 uncaught constant negative shift | stdout/exit same; stderr `ValueError: negative shift count` (base typed build printed bare `ValueError`) |
| q9 indirect `//` (no shift) | output same; C differs (typed clone dropped) — see note |
| q10 direct+list+nested-lambda shift | same |
| q11 div/mod/true-div via callback | same |
| q12 200k caught shifts | same; max RSS 1.2 MB, no leak/crash |
| q13 `int("x")` in parallel body | refused identically by both builds |
| q14 `1<<63`, `1<<64` | differs on **both** builds → pre-existing, acknowledged |
| q15 typed uncaught negative shift | same; base differs (bare `ValueError`) |
| q16 div edges via callback | only pre-existing modulo message differs on **both** (base identical) |
| parallel `<<`,`>>`,`<<=`,`>>=` × `AIL_THREADS=1/2/4/8`, uncaught | all correct, exit 1 with `ValueError: negative shift count`; general build refuses identically on base |
| q6 bound-method extraction | `AttributeError` on **both** builds → pre-existing |

**Pre-existing (not blocking):** int64 `1<<63`/`1<<64` overflow; bound-method extraction (`f = c.m`) unsupported; `5 % 0` message `integer division or modulo by zero` vs CPython `integer modulo by zero`. All identical on base.

**Claims:** worker trap/message re-raise — verified; 1/2/4/8-thread + uncaught — verified; general build cannot compile `parallel for` and refuses identically on base — verified; only `shift_overflow` differs — mostly verified (q6/q16 add more pre-existing diffs); tests pre171 17.9 s and safetynet 102.0 s pass — verified; files/corpus_findings3/parallel_for — unverified (not re-run per review scope); `--check` manifest — verified; not pushed — verified.

**Speed:** `perf_event_open` unavailable, as reported. Candidate sets identical base↔HEAD for all 18 gdev files containing shifts, and for 41 sampled non-shift gdev files.

**Note (not a defect):** the rejection is general to all trap-capable functions, so a non-shift indirect helper (q9) also loses its typed clone; output matches CPython and gdev candidate sets are unchanged, and this is stated in DEVLOG.

**Unverified:** worker's own 20 probes; `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_parallel_for`; direct instruction counts.

VERDICT: ACCEPT
[cost $0.0464, opencode tokens {"total": 2141891, "input": 114655, "output": 11207, "reasoning": 27549, "cache.write": 0, "cache.read": 1988480}]
    tool time: bash 3.7 min
        103s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_safe
         19s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre1
         18s bash   cd /tmp/rprobes && for p in q1_lambda_list q2_callback_dict_attr q3_shift_forms q4_direct_try q5_no_feature; d
         15s bash   cd /home/runner/work/ail-ci/ail-ci && n=0; for f in ~/corpus/gdev/*.py; do if grep -qE '<<|>>' "$f"; then cont
          9s bash   cd /tmp/rprobes && cat > q8_uncaught_const.py <<'EOF' print("before") print(1 << -1) print("after") EOF cat > 
          8s bash   cd /home/runner/work/ail-ci/ail-ci && for f in $(grep -rlE '<<|>>' ~/corpus/gdev/*.py); do b=$(python3 AIL_CUR
          7s bash   cd /tmp/rprobes && echo "== q1 base"; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/q1_lambda_list.py /tmp/base
          6s bash   cd /tmp/rprobes && cat > q16_div_edges.py <<'EOF' def fdiv(a, b):     return a // b  def fmod(a, b):     retur

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T22:01:14Z
