# job job-fuzz94-10241847  started 2026-10-24T09:54:39Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":115652,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":115411,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Fixed:** nested `def` with a mutable literal default silently rebuilt the default per call (`f(1), f(2)` → `[1] [2]`; CPython → `[1] [1, 2]`). The general path now refuses it by name on both builds.

- First silent difference: `/tmp/probes/p81.py`.
- Regression test: `AIL_CURRENT/test_ail_fuzz94.py`, registered in `ail_check.MODULES`.
- Records: `DEVLOG.md`, `DIFFERENCES.md` row `C?-job-fuzz94-10241847-1`; manifest `--check` passes.
- Commit: `bb18442`.

**Tests on final commit:** 38 run, 1 skipped, OK in 469.58s — `test_ail_fuzz94`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_nested_functions`.

**Self-check probes:** p84–p87 and p90 (empty list/dict/set, tuple-of-list, recursive list default) refused by name on both builds; p82–p83 (returned/loop nested mutable defaults) and p88–p89 (top-level/method defaults) match CPython; p81 now refused. Earlier probes p01–p80 matched or were refused.

**Other differences seen (not fixed):** `**kwargs` calls, positional-only parameters, non-constant defaults in nested defs, caught `RecursionError`, and `__defaults__` access are refused by name; a nested `def` inside a top-level loop and used after the loop fails with `name 'f' is not defined`; duplicate/unknown/missing keywords are refused. No other silent stdout differences.
[cost $0.0000, opencode tokens {"total": 5976228, "input": 265028, "output": 20362, "reasoning": 23126, "cache.write": 0, "cache.read": 5667712}]
    tool time: bash 13.3 min, edit 0.0 min
        470s bash   python3 -m unittest AIL_CURRENT.test_ail_fuzz94 AIL_CURRENT.test_ail_safetynet AIL_CURRENT.test_ail_files AIL_
         64s bash   python3 - <<'PY' from pathlib import Path d=Path('/tmp/probes') progs={ 'p11':'''def rec(n, acc=[]):     acc.a
         49s bash   python3 - <<'PY' from pathlib import Path d=Path('/tmp/probes') progs={ 'p41':'''def outer():     fs = []     
         36s bash   for p in /tmp/probes/p*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1; done > /tmp/probes/run1.
         35s bash   python3 - <<'PY' from pathlib import Path d=Path('/tmp/probes') progs={ 'p31':'''fs = [] for i in range(3):   
         34s bash   python3 - <<'PY' from pathlib import Path d=Path('/tmp/probes') progs={ 'p69':'''def main():     fs = []     i
         27s bash   python3 - <<'PY' from pathlib import Path d=Path('/tmp/probes') progs={ 'p61':'''def main():     fs = []     x
         20s bash   python3 - <<'PY' from pathlib import Path d=Path('/tmp/probes') progs={ 'p84':'''def main():     def f(acc=[])

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change does (one line):** In the general-path nested-def registration, it adds `_literal_default_is_mutable()` and raises `Unsupported` for a nested `def` whose positional or keyword-only default is a list/dict/set (or tuple containing one); no runtime or emitter behaviour is changed otherwise.

### Claims vs observation
- “Nested mutable literal default now refused by name on both builds” — **verified** (p1, p4–p6, p8, p9, p14, p20–p21, p24, p28: general and default builds both fail with `mutable literal default`).
- “Base printed `[1] [2] [3]`” — **verified** (base p1 gives `[1] [2] [3]`, CPython `[1] [1, 2] [1, 2, 3]`).
- “Escaping/returned/loop nested defs with mutable defaults and recursion agree” — **verified** (p2, p3, p12, p15, p22, p25, p26 match CPython both builds).
- “Top-level/method defaults and immutable defaults agree” — **verified** (p7, p10, p27, worker p88 match; p28 tuple-of-list refused).
- “Test registered in `ail_check.MODULES`; DEVLOG/DIFFERENCES row; manifest check” — **verified** (diff; `update_manifest.py --check` rc 0).
- “Commit bb18442” — **verified**.
- “Tests on final commit, incl. 38 run/1 skipped” — **partially verified**: `test_ail_fuzz94`, `test_ail_safetynet`, `test_ail_corpus_findings3`, `test_ail_nested_functions` all pass on HEAD; `test_ail_files` not re-run; run/skip counts not verified.
- “Other differences (kwargs, posonly, loop-def-after-loop, duplicate keywords)” — **unverified** (spot-check: keyword call through a function value is indeed refused, p23).

### Probe summary
Refused by name on HEAD: p1, p4, p5, p6, p8, p9, p13, p14, p20, p21, p24, p28 (and worker p84–p87, p90).
Matched CPython on HEAD: p2, p3, p7, p10, p11, p12, p15, p16, p17, p19, p22, p25, p26, p27 (and worker p81/p82/p83/p88/p89).
No-feature program: `--debug-dir/program.c` byte-identical between base and HEAD.

### Pre-existing (not blocking)
- p18: attribute call on an instance (`box.f(...)`) refused identically on base — unrelated.
- p23: keyword arguments through a function value refused identically on base — unrelated.
- p13: base silently gave `[1] [2]`; HEAD now refuses it (improvement, same root cause).

### Unverified
- Exact worker test counts and `test_ail_files`.
- The full list of p01–p80 outcomes and the reported loop-def NameError case.
- Speed: not measured; the helper runs once per nested def at compile time, so no runtime hot path changes.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 582537, "input": 39893, "output": 6262, "reasoning": 12734, "cache.write": 0, "cache.read": 523648}]
    tool time: bash 8.6 min
        146s bash   cd AIL_CURRENT && date && timeout 800 python3 ../tools/par_check.py -j 2 test_ail_nested_functions 2>&1 | tail
        142s bash   cd AIL_CURRENT && date && timeout 800 python3 ../tools/par_check.py -j 2 test_ail_corpus_findings3 2>&1 | tail
         91s bash   cd AIL_CURRENT && date && timeout 800 python3 ../tools/par_check.py -j 2 test_ail_fuzz94 test_ail_safetynet 2>
         41s bash   date; for p in /tmp/rprobes/p*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | sed -n '1,12p'; 
         21s bash   cat > /tmp/rprobes/p15.py <<'EOF' def main():     fs = []     for i in range(3):         def f(x, acc=[]):    
         16s bash   for p in /tmp/rprobes/p1.py /tmp/rprobes/p2.py /tmp/rprobes/p15.py /tmp/rprobes/p18.py /tmp/rprobes/p19.py; do
         14s bash   for p in /tmp/probes/p84.py /tmp/probes/p85.py /tmp/probes/p86.py /tmp/probes/p87.py /tmp/probes/p90.py; do ec
         13s bash   for p in /tmp/probes/p88.py /tmp/probes/p89.py /tmp/probes/p82.py /tmp/probes/p83.py; do echo "===== $p"; bash

FINAL VERDICT: ACCEPT  2026-10-24T10:30:36Z
