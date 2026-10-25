# job job-pre181-10251538  started 2026-10-25T06:39:11Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":363,"duration_api_ms":234,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":329,"duration_api_ms":205,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fix committed: `e9270ac` (on `job-pre181-10251538`, not pushed).

- Fixed `p_stopiter`: `@contextmanager.__exit__` now re-raises a sent `StopIteration` like CPython, while a replacement `StopIteration` still yields PEP 479 `RuntimeError`.
- `p_tb` remains a pre-existing difference; recorded as open (`C?-job-pre181-10251538-2`).
- Added `test_ail_pre181.py` (3 programs × 2 builds, 20s) and registered it in `ail_check`/`ci_shards`.
- Probes in `/tmp/probes`: `p_stopiter_a`–`n`, `p_si1`–`p_si10`, `p_tb`, `p_cause_hidden`, `p_isinst`. All match CPython except `p_stopiter_e`/`n` (refused by name, as before), `p_cause_hidden` (pre-existing named chain refusal), and `p_tb` (known open difference).
- Final-commit tests (`-j 2`): `test_ail_pre181`, `test_ail_pre179`, `test_ail_fuzz56`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 281s, 0 failed.
- Manifest `--check` passes; JSON parses; `git diff --check` clean.
[cost $0.0000, opencode tokens {"total": 6207958, "input": 148687, "output": 14924, "reasoning": 26811, "cache.write": 0, "cache.read": 6017536}]
    tool time: bash 19.1 min
        373s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre181 test_ail_pre179 test_ail_fuzz56 test_ail_
        283s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre181 test_ail_pre179 test_ail_fuzz56 test_ail_
        143s bash   for p in /tmp/probes/p_stopiter_*.py /tmp/probes/p_si*.py /tmp/probes/p_tb.py /tmp/probes/p_cause_hidden.py /t
         80s bash   for p in /tmp/probes/p_si*.py /tmp/probes/p_stopiter_k.py /tmp/probes/p_cause_hidden.py /tmp/probes/p_tb.py; d
         64s bash   cat > /tmp/probes/p_si1.py <<'EOF' from contextlib import contextmanager  @contextmanager def cm(tag):     yie
         36s bash   mkdir -p /tmp/probes cat > /tmp/probes/p_stopiter_a.py <<'EOF' def g():     try:         raise StopIteration("
         35s bash   cat > /tmp/probes/p_cause_hidden.py <<'EOF' def g():     raise StopIteration("x")  def f(name):     try:      
         34s bash   cat > /tmp/probes/p_stopiter_h.py <<'EOF' def g():     yield 1     raise StopIteration("after")  for x in g():

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of job-pre181 (commit e9270ac)**

What the change really does: in `safetyrt.py`, a PEP 479 conversion of an escaping `StopIteration` now stores that exact object as a hidden attribute (`AIL_ATTR_GEN_CAUSE = -2`) on the new `RuntimeError`; `_AilGenCM.__exit__` uses the new `_ail_exc_cause_is` primitive to follow CPython `contextlib`'s `exc.__cause__ is value` check and returns `False`, so the `with` re-raises the original `StopIteration`. Plus test, registration, DEVLOG and an open DIFFERENCES row for `tb=None`. Matches the report.

**Probes (my `/tmp/rprobes`, both builds unless noted):**
- `p1_basic` inline empty/msg StopIteration, `MyStop` subclass, args/str/identity: match.
- `p2_rethrow_same` generator catches sent SI and bare `raise`: original object comes back (`e is err` True): match.
- `p3_rethrow_new` new SI / new subclass from handler → `RuntimeError generator raised StopIteration`: match.
- `p4_suppress_return`, `p5_nested`, `p11_finally`: match.
- `p6_sources` arg / list item / attribute / dict value: all match; mutating `.args` after catching still shows old message — identical on base (pre-existing, see below).
- `p7_raw_gen` PEP 479 outside contextmanager: match.
- `p8_no_feature`: match; `--debug-dir program.c` is byte-identical to base (only temp paths differ in `native_report.json`).
- `p9_stress` 20k contextmanager SI exits: match, no crash.
- `p13_identity_eq`, `p14_surface` (repr/args/`vars`, hidden attr not exposed): match.
- `p10_multinherit`: refused by name (pre-existing limitation).
- Worker probes rerun: `p_si1..10`, `p_stopiter_a..m` (except e/n) all match; `p_stopiter_e/n` refused by name on both HEAD and base; `p_cause_hidden` differs identically on base.

**Claim check:**
- p_stopiter fixed: verified — HEAD matches CPython, base prints `RuntimeError` on both builds.
- p_tb open/recorded: verified — differs on base and HEAD identically; `C?-job-pre181-10251538-2` row present.
- test_ail_pre181 added, registered (`ail_check`, `ci_shards`, MANIFEST): verified; runs 20.2s.
- Final-commit tests: verified by rerun — `test_ail_pre181`, `test_ail_pre179`, `test_ail_fuzz56`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, 0 failed.
- Manifest `--check`, JSON parse, `git diff --check`: verified. DEVLOG says 371s vs report 281s (minor, not material).
- No hot path: verified — only `g15_036.py` uses `@contextmanager` in `~/corpus/gdev` and it is refused by name on base and HEAD (g15_008 only uses `suppress`).

**Pre-existing (identical on /tmp/base):** `__exit__` receives `tb=None`; mutating `e.args` does not change `str(e)`; `__cause__`/`__context__` reads are refused; `.throw()` and multiple-inheritance refusals.

**Unverified:** instruction counts/speed — `icount` cannot run here (`perf_event_open: Permission denied`); full suite deliberately not run per instructions.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1671231, "input": 62505, "output": 9777, "reasoning": 19429, "cache.write": 0, "cache.read": 1579520}]
    tool time: bash 11.2 min
        209s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
        124s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         86s bash   date; cd /tmp; for p in p_si1 p_si2 p_si3 p_si4 p_si5 p_si6 p_si7 p_si8 p_si9 p_si10 p_stopiter_k p_stopiter_e
         51s bash   date; cd /tmp; for p in p_stopiter_a p_stopiter_b p_stopiter_c p_stopiter_d p_stopiter_f p_stopiter_g p_stopit
         48s bash   cd /tmp/rprobes && sed -i 's/BaseException/Exception/g' p1_basic.py p3_rethrow_new.py p4_suppress_return.py p5
         48s bash   date; cd /tmp/rprobes; for p in p1_basic p2_rethrow_same p3_rethrow_new p4_suppress_return p5_nested p6_source
         20s bash   cd /tmp/rprobes && cat > p1_basic.py <<'EOF' from contextlib import contextmanager  class MyStop(StopIteration
         18s bash   date; echo "== base p12"; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/p12_argmutate.py /tmp/base 2>&1 | grep 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T08:33:50Z
