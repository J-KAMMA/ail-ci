# job job-fz1-10281147  started 2026-10-28T02:48:04Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"2621cce2-efec-498d-bff5-9cefe0183800","session_id":"fa282653-27d8-4416-8f2c-146e5474f81f"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"18cc13e1-0556-4978-ab84-f5d851f43b3a","session_id":"3a9f5adb-d325-4844-8dbf-d0f245292e5f"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `4fb2c64`.

**Cause.** The general emitter (`pyboxed2.py`, `stmt_Try`) emitted a try's `else` statements inside the same C block as the try body, so the try's own `except` clauses caught exceptions raised in `else`. CPython lets them reach an outer handler. The minimized construct was:

```python
try:
    pass
except ValueError:
    print('caught')
else:
    print(int('Cd'))
print('after')
```

**Fix.** `else` now jumps past the handler dispatch and is compiled after it, against enclosing handlers. With a `finally`, it remains inside the finally trampoline, so the finally runs and the exception then propagates outward. Matched handlers and body errors skip `else`; normal completion runs it once.

**Probes** (both builds via `cmp.sh`): original `fz1` reproducer, `p_tryelse`, `p_tryelse2`, `p_tryelse3`; plus `IndexError`/`ZeroDivisionError`/`KeyError`/`RuntimeError` in `else`, nested else, success path, body-error-skips-else, and values through an argument, list item, attribute and dict value — all match CPython. `return`/`break`/`continue` in `else` with `finally` also checked; `break`/`continue` remain refused by name on the general path (pre-existing).

**Tests:** `test_ail_fz1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Also `test_ail_finally`, `test_ail_reraise`, `test_ail_exception_resources` — 3 modules, 0 failed. `update_manifest.py --check` passes.

**Other differences:** none observed in this reproducer.
[cost $0.0000, opencode tokens {"total": 4452649, "input": 107016, "output": 14385, "reasoning": 19824, "cache.write": 0, "cache.read": 4311424}]
    tool time: bash 15.3 min
        383s bash   python3 tools/par_check.py -j 2 test_ail_fz1 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 
        131s bash   python3 -u - <<'PY' import ast, subprocess, os, tempfile, shutil src=open('/tmp/probes/fz1.py').read() lines=s
        120s bash   python3 - <<'PY' import ast, subprocess, os, tempfile, shutil src=open('/tmp/probes/fz1.py').read() lines=src.
         33s bash   cd AIL_CURRENT && python3 -B -m unittest test_ail_fz1 -v 2>&1 | tail -30
         31s bash   for p in p_tryelse p_tryelse2 p_tryelse3 fz1; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py $PWD > /
         28s bash   mkdir -p /tmp/probes/fz1x cat > /tmp/probes/fz1x/return_else.py <<'PYEOF' def f():     try:         x = 1     
         27s bash   python3 tools/par_check.py -j 2 test_ail_finally test_ail_reraise test_ail_exception_resources 2>&1 | tail -20
         23s bash   mkdir -p /tmp/probes; cat > /tmp/probes/fz1.py <<'PYEOF' def h0(a: int, b: int) -> int:     v1: int = ((a * b)

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `4fb2c64` (`git diff work..HEAD`).

**What the diff really does.** In `pyboxed2.py::stmt_Try`, `else` statements are no longer emitted inside the try body's C block: the body jumps to a `tryelse` label placed after handler dispatch, so an exception in `else` goes to the enclosing handler (and, with `finally`, through the existing trampoline so `finally` still runs first). Matches the report.

**Probes** (`/tmp/rprobes`, both builds via `cmp.sh`, base `/tmp/base`):
- `fz1` reproducer: both builds now match CPython (stdout+exit 1); base general differed.
- `p1,p3,p13,p15,p23,p25,p28` (else raises → outer handler / outer finally / function boundary / loop): HEAD matches; base `p1,p13,p28` reproduce the bug (own handler catches `else`).
- `p2,p7,p14,p16,p22` (return in else, finally, finally-return overrides, outer finally): match.
- `p4,p5,p8,p17,p18,p19,p26,p27` (normal else, finally raising, nested else, body-error/matched-handler skips else, attr/dict/list values, assert, loop exit): match.
- `p9,p11,p12,p20` (dict value, break/continue in else without finally): match.
- `p6` (`continue` in else with `finally`) and `p24` (`break` in else over outer `finally`): named compile-time refusal on the general path, identical on base → pre-existing, not a defect.
- `p10,p21` (no `try/else`): `--debug-dir` `program.c` byte-identical to base.

**Report claims.** Cause verified; fix verified; "both builds match" verified for equivalents of all claimed cases; 4-module test run verified (0 failed); extra `test_ail_finally`, `test_ail_reraise`, `test_ail_exception_resources` 0 failed; `update_manifest.py --check` clean; "no other differences in reproducer" verified. Break/continue refusal confirmed pre-existing.

**Speed.** Not a hot-path change; programs without `try/else` emit identical C. The two `~/corpus/gdev` files with `try/else` I tried (`g15_036`, `g15_012`) are refused on the general path on both trees (pre-existing), so no icount comparison was possible.

**Unverified.** The worker's own probe files and its claimed instruction counts are not present; I re-derived the behaviour with my own probes instead.

**Pre-existing.** Named refusals for `break`/`continue` leaving a `try/finally` region on the general path; refused the same on `work`.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 772996, "input": 34695, "output": 5961, "reasoning": 10932, "cache.write": 0, "cache.read": 721408}]
    tool time: bash 8.2 min
        282s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_fz1 test_ail_
         39s bash   cd /tmp/rprobes && for p in p1 p2 p3 p4 p5 p6 p7 p8 p9 p10; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/rprob
         37s bash   cd /tmp/rprobes && for p in p11 p12 p13 p14 p15 p16 p17 p18 p19 p20; do echo "===== $p"; bash ~/tools/cmp.sh /
         27s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 tools/par_check.py -j 2 test_ail_finally test_
         22s bash   cd /tmp/rprobes && python3 - <<'PY' import re text=open('/home/runner/work/_temp/review0.md').read() m=re.sear
         21s bash   cd /tmp/rprobes && for p in p1 p6 p10 p13 p16; do echo "===== base $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py
         16s bash   cd /tmp && cc -O2 -w -include signal.h -include stdlib.h -o icount /home/runner/work/ail-ci/ail-ci/tools/icoun
         11s bash   cd /tmp/rprobes && cat > p25.py <<'EOF' def g():     try:         try:             pass         except ValueEr

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T04:35:56Z
