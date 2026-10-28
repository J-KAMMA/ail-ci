# job job-pre381-10281228  started 2026-10-28T03:28:49Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"01844316-845f-4df4-82bd-436ed88bf20a","session_id":"4f9724a1-1259-48d1-a70f-da6bd126a12f"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"f654d68a-0e83-49ea-9cfe-60c538a2e268","session_id":"3626bb1a-72ba-4284-9f41-a46043c8a0ea"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `02e662d`.

**Cause:** the pre381 class-name check emitted `if (g_class_init_arr[i]) ...` before an `except` type, turning a later handler into that check's `else if`. After an earlier handler caught the exception, control fell into `else { goto leave; }`.

**Fix:** each handler now jumps explicitly to the try end (or `finally`) after its body, so later handlers are never tried after a match. Files: `pyboxed2.py`, `test_ail_pre381.py`, `MANIFEST.json`, `DEVLOG.md`.

**Tests on final commit:** `test_ail_multifile`, `test_ail_pre381`, `test_ail_try_locals`, `test_ail_try_hoist`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 69 tests, OK (1 skipped). Manifest `--check` passes.

**Probes** (`/tmp/probes/pre381fix_p01`–`p08`, both builds):
- p01 loop/two handlers, p02 argument/list/dict/attribute routes, p03 finally, p05 later handler skipped, p06 nested/break, p07 tuple handlers, p08 empty loop: match CPython.
- p04 unbind/continue: default build matches; general build refused by name (`continue out of a try/finally`).
[cost $0.0000, opencode tokens {"total": 3673825, "input": 89408, "output": 11176, "reasoning": 16889, "cache.write": 0, "cache.read": 3556352}]
    tool time: bash 17.6 min
        546s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_multifile test_ail_pre381 test_ail_try_locals test_ail_try_h
        118s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre381 test_ail_try_locals test_ail_try_hoist 2>&1 | tail -1
        101s bash   cat /tmp/pre381.log | head -40; echo "---rerun---"; cd AIL_CURRENT && python3 -m unittest -q test_ail_pre381 2
         80s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_multifile 2>&1 | tail -80
         47s bash   cd AIL_CURRENT && (python3 -m unittest -q test_ail_multifile > /tmp/multifile.log 2>&1; echo $? > /tmp/multifi
         39s bash   tail -20 /tmp/try_hoist.log; ls AIL_CURRENT/test_ail_try_hoist.py 2>&1; cd AIL_CURRENT && python3 -m unittest 
         33s bash   cd /tmp/probes && for p in pre381fix_p01_loop_two_handlers pre381fix_p02_routes pre381fix_p03_finally_loop pre
         23s bash   cd AIL_CURRENT && (python3 -m unittest -q test_ail_try_locals > /tmp/try_locals.log 2>&1; echo $? > /tmp/try_l

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Change:** In `stmt_Try` (python/pkg-v12/pyboxed2.py:11683), each handler body now ends with an explicit `goto` to the try end (or `finally`), so later handler conditions—including the pre381 class-bound check emitted before a class-name `except`—are not evaluated after an earlier handler matched. Adds two regression cases in `test_ail_pre381.py`, updates MANIFEST/DEVLOG.

**Claims check**
- Commit `02e662d` present — verified.
- Cause (class-name `if` steals the following `else if`; fall-through reaches `else { goto leave; }`) — verified: p1/p13/p14/p15/p17 fail on `/tmp/base`, match on HEAD.
- Fix description and file list — verified against the diff.
- Tests: `test_ail_multifile`, `test_ail_pre381`, `test_ail_safetynet` all pass on HEAD (`parallel -j 2`, 174s). The other modules in the 69-test claim were not re-run.
- Worker probe p04: general build refused by name, default matches — verified. Other worker probes not re-run; equivalent shapes covered below.
- Manifest `--check` — verified (rc 0).

**My probes** (`/tmp/rprobes`, both builds via `cmp.sh`, all match CPython unless noted)
- p1/p2: two handlers, first match skips later (incl. unbound class name); p13 unbind route; p14 loop/continue; p15 finally; p17 tuple classes; p18 mixed builtin; p5 nested; p6 else/clause; p7 empty handlers; p8 re-raise+finally; p10 arg/list/attr/dict routes; p11 bare-except chain; p19/p20 return in handler/finally; p21 exception in handler with finally. All same stdout/exit.
- p12 (no try) `--debug-dir` C identical to base; only temp paths differ in the report.

**Pre-existing** (identical on `/tmp/base` → non-blocking)
- p3: `repr(KeyError('k'))` is `KeyError("'k'")` on both base and HEAD.
- p9: unbound class in an `except` that is actually reached prints the original exception instead of `NameError`, on both base and HEAD.
- p16: invalid Python (`except:` not last) is accepted by AIL on both; HEAD only loses the old spurious NameError.

**Unverified**
- Speed: `tools/icount.c` build succeeded but `perf_event_open` was denied in this environment.
- `test_ail_try_locals`, `test_ail_try_hoist`, `test_ail_files`, `test_ail_corpus_findings3` (outside the reviewer's required module set).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 815077, "input": 93101, "output": 5482, "reasoning": 11982, "cache.write": 0, "cache.read": 704512}]
    tool time: bash 5.1 min
        176s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 tools/par_check.py -j 2 test_ail_pre381 test_
         40s bash   cd /tmp/rprobes && cat > p8.py <<'EOF' def f():     try:         try:             raise ValueError("v")       
         22s bash   cd /tmp/rprobes && cat > p16.py <<'EOF' def f():     try:         raise ValueError("x")     except:         pr
         21s bash   cd /tmp/rprobes && cat > p13.py <<'EOF' class A(Exception):     pass class B(Exception):     pass def f(flag):
         10s bash   cd /tmp/rprobes && for p in p3 p9 p12; do echo "=== BASE $p ==="; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp/
         10s bash   cd /tmp/rprobes && cat > p19.py <<'EOF' def f():     try:         raise ValueError("v")     except ValueError:
          8s bash   date; cd /tmp/rprobes && for p in p1 p2; do echo "=== BASE $p ==="; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tm
          8s bash   cd /tmp && grep -c "except\|try:" ~/corpus/gdev/g14_024.py ~/corpus/gdev/g07_038.py; cc -O2 -w -include signal

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T05:15:24Z
