# job job-pre109-10242222  started 2026-10-24T13:23:21Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":722,"duration_api_ms":598,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":612,"duration_api_ms":486,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Commit `fc7fa3d` on `job-pre109-10242222`.

Fixed the pre-existing typed-shift difference: `ck_shl`/`ck_shr` now raise `ValueError: negative shift count` using `ail_raise_value_adopt` (no leak), and `pymix` treats non-literal shift counts in `BinOp`/`AugAssign` as ValueError traps so boxed `try` blocks keep their handler. Added `AIL_CURRENT/test_ail_pre109.py`, DEVLOG/DIFFERENCES entries, manifest refresh.

Probes (`bash ~/tools/cmp.sh`, both builds):
- `pre109_neg_shift.py` — constants, argument, list, attribute, dict, augmented shifts: match CPython, exit 0.
- `pre109_uncaught.py` — exit 1, `ValueError: negative shift count` on both.
- `pre109_valid.py` — valid left/right shifts including counts ≥64: match.
- `pre109_leak.py` — 1,000,000 caught shifts: output matches, maxrss 11,564 KB.

Tests on final commit: `test_ail_pre109`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4, 0 failed (279 s); extra `bugs7`, `mixed_bounds`, `unified`, `instruction_gap`, `cov2` — 5/5, 0 failed (409 s). `update_manifest.py --check` rc=0.

Not changed: pre-existing int64 left-shift overflow above 63 bits, and indirect function-value shift dispatch (lambda held in a list) remains on the same pre-existing mixed-mode limitation.
[cost $0.0000, opencode tokens {"total": 7172585, "input": 144992, "output": 14658, "reasoning": 25543, "cache.write": 0, "cache.read": 6987392}]
    tool time: bash 17.0 min, edit 0.0 min
        411s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_bugs7 test_ail_mixed_bounds test_ail_uni
        281s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre109 test_ail_safetynet test_ail_files
        222s bash   cd AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findi
         24s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 -m unittest -v test_ail_pre109 2>&1 | tail -80
         21s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 -m unittest -v test_ail_pre109 2>&1 | tail -120
         19s bash   cat > /tmp/probes/pre109_neg_shift.py <<'EOF' class Box:     def __init__(self, n):         self.n = n  def by
         10s bash   cat > /tmp/probes/pre109_uncaught.py <<'EOF' print(1 << -1) EOF cd /home/runner/work/ail-ci/ail-ci && for p in
          6s bash   cat > /tmp/probes/pre109_neg_shift.py <<'EOF' class Box:     def __init__(self, n):         self.n = n  def by

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — pre109 (`fc7fa3d`)

**What the diff does.** In `pyfront.py`, the negative-count branch of `ck_shl`/`ck_shr` now raises a message-bearing `ValueError` (`"negative shift count"`) through `ail_raise_value_adopt` instead of `ail_raise_named`; in `pymix.py`, a `BinOp`/`AugAssign` shift whose count is not a non-negative literal is classified as a `ValueError` trap. Records/test/manifest are updated. This matches the report; only nuance is that the trap only protects direct call sites (see pre-existing below).

**Probes** (`~/tools/cmp.sh`, both builds, compare with `/tmp/base` where noted):
- `r6` direct functions, arguments, `<<=`, `>>=` under a boxed `try`: HEAD both builds match CPython; **base default fails** (uncaught empty `ValueError`, exit 1). Fix confirmed.
- `r9`/`r11` typed-internal catches of negative literal/argument/list/dict/attribute counts: HEAD `21 21` matches CPython; base `0 0` (empty message).
- `r4`/`r10` uncaught: exit 1, `ValueError: negative shift count` both HEAD builds.
- `r2` non-int operands (`float`, `str`, `None`, `bool`): matches CPython both builds.
- `r3`/`r7` valid shifts, counts ≥64, multi-hop calls: match.
- `r5` shift-free program: `--debug-dir` `program.c` byte-identical to base (native_report differs only in temp paths).
- Typed-internal 1,000,000 caught shifts: maxrss 1256 KB vs base 1252 KB — no leak.
- Worker's `pre109_lambda_list_tmp.py` and shift-overflow probe: differ from CPython on HEAD **and identically on base**.

**Report claims.** Negative-count message/adopt: verified. Direct-call mixed-mode handler: verified (`r6`). “No leak”: verified with the typed-internal probe. Manifest `--check` rc=0: verified. Tests: I ran `par_check -j 2 test_ail_pre109 test_ail_safetynet` → 2/2 pass, 121 s; `test_ail_files`/`test_ail_corpus_findings3` not re-run (review scope). Their exact maxrss figure and extra 5-module batch: unverified but not contradicted.

**Pre-existing (identical failure on base).**
- A shift reached through a lambda held in a list still escapes the caller's boxed `try` on the default build (`r1`, worker's `pre109_lambda_list_tmp.py`): base and HEAD both stop after the first two cases; HEAD only adds the message. This is the acknowledged indirect-dispatch limitation.
- int64 left-shift overflow above 63 bits (worker's `pre109_shift_overflow.py`) differs on both base and HEAD.

**Speed.** `perf_event_open` is denied, so instruction counts are unavailable. A 400M-iteration synthetic shift-under-`try` loop timed HEAD 0.24 s vs base 0.25 s, and `pymix` candidate sets are unchanged for all 14 gdev shift programs, so no measured regression. Note: an identical fix already exists on the unmerged pre85 branch (`bdea807`, `4af8dc8`); this branch’s version uses `adopt` and therefore avoids the leak that variant had.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2841659, "input": 84434, "output": 10342, "reasoning": 26115, "cache.write": 0, "cache.read": 2720768}]
    tool time: bash 4.1 min
        123s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         22s bash   date; for p in /tmp/rprobes/r*.py; do echo "=== $p"; bash ~/tools/cmp.sh $p $PWD 2>&1 | grep -E "cpython exit|
         10s bash   date; for p in /tmp/probes/pre109_neg_shift.py /tmp/probes/pre109_uncaught.py /tmp/probes/pre109_valid.py; do 
          9s bash   date; for p in /tmp/probes/pre109_lambda_tmp.py /tmp/probes/pre109_lambda_list_tmp.py /tmp/probes/pre109_shift
          7s bash   cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount /home/runner/work/ail-ci/ail-ci/tools/icount.c &&
          7s bash   date; bash ~/tools/cmp.sh /tmp/rprobes/r1.py /tmp/base 2>&1 | tail -50; date
          7s bash   bash ~/tools/cmp.sh /tmp/rprobes/r1.py $PWD 2>&1 | tail -60
          6s bash   date; for p in /tmp/probes/pre109_lambda_list_tmp.py /tmp/probes/pre109_shift_overflow.py; do echo "=== $(base

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T15:05:42Z
