# job job-cpyhyb1-11012125  started 2026-11-01T12:27:23Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all four review defects in `AIL_CURRENT/ail_cpython_hybrid.py`:

- Concurrent overflow: mixed-mode `jmp_buf` and save pointer are now `__thread`; 8 threads x 5000 calls matched CPython, exit 0.
- Buffer leaks: every later-argument/list/scalar failure now jumps to `fallback:` and frees once; 50k-call probe stayed at CPython RSS (hybrid 10,412 KB vs CPython 10,540 KB).
- Metadata: wrapper code now carries the original `co_name`, `co_varnames` including locals, `co_nlocals`, filename/first line; no `__wrapped__`.
- Helper hygiene: generated names are chosen against the parameter list, so `_ail_hybrid_invoke`/`_ail_hybrid_native_ref`/`_ail_hybrid_original_ref` parameters work.

Tests: `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` rc 0. Committed as `7157259`.
[cost $0.0000, opencode tokens {"total": 3583781, "input": 191369, "output": 15512, "reasoning": 16900, "cache.write": 0, "cache.read": 3360000}]
    tool time: bash 5.7 min
        290s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1100 python3 tools/par_check.py -j 2 test_ail_cpython_hybrid tes
         18s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_c
         14s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_c
          3s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/fixprobe && mkdir -p /tmp/fixprobe && cat > /tmp/fixprobe/p.
          2s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -c " import sys, tempfile sys.path.insert(0,'.') imp
          2s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/fixprobe3 && mkdir -p /tmp/fixprobe3 && cat > /tmp/fixprobe3
          2s bash   cd /tmp/fixprobe3b && cat > run.py <<'PY' import sys, resource sys.path.insert(0, '/tmp/fixprobe3b/out') impor
          2s bash   cd /tmp/fixprobe3b && python3 - <<'PY' import sys sys.path.insert(0,'/tmp/fixprobe3b/out') import tgt print(tg

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change actually does:** In the hybrid only, `7157259` makes each unit's overflow flag, `jmp_buf` and save pointer `__thread`; routes every wrapper conversion failure to the single `fallback:` free path; rewrites the wrapper `__code__` to the original's `co_name`/`co_varnames`/`co_nlocals`/filename/line; and picks helper globals not shadowed by parameters. Adds tests/docs. This matches the report.

**Probes** (`/tmp/rprobes`, HEAD hybrid build, vs CPython):
- `thr` (defect 1): 8 threads x 5000 `mul` over `3037000500`, `2**40`, `2**62`, etc. → exit 0, all assertions, hash `-4716812056682207494` = CPython. Fixed. Generated C shows both `jmp_buf` and save pointer changed to `__thread`.
- `leak` (defect 2): 50k `f(list(range(1000)), (2,))` → hybrid RSS 12,332 KB vs CPython 10,532 KB, constant at 10k/100k; p3/p4/p5 scalar, bool, list-element, tuple and overflow fallbacks at 100k all stay ~12.3 MB. No leak. The report's exact 10,412/10,540 numbers were not reproduced (hybrid is ~1.8 MB higher fixed extension overhead), but the "stays at CPython RSS" substance holds.
- `r13` (defect 3): `4 ('n', 'z', 'w') f`, `__wrapped__` False, signature `(n: int) -> int` = CPython. Fixed.
- `r27` (defect 4): parameters named `_ail_hybrid_*` plus double-underscore variants → `6 15` = CPython. Fixed.
- `p1`–`p11`: list+str return, two-list aliasing/empty/negative, list element overflow, wrong bool/int types, tuple second argument, metadata with defaults/locals, no-arg, helper-name collisions in locals, values via attribute/dict, mutation after call, and arity/keyword `TypeError`s: all stdout/exit equal CPython.
- `p8` concurrency: 8 x 20,000 mixed `mul`/`add`/`fl`/`cat`/`total` incl. overflow and list fallbacks → exit 0, output equal CPython.

**Claims:** all four fix claims verified. `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed; 7/7 hybrid tests ran. `update_manifest.py --check` rc 0. HEAD is `7157259`. Default standalone `program.c` is byte-identical to `/tmp/base` and the compiled executable sha256 is identical.

**Pre-existing (reproduce on `/tmp/base`, not caused by this change):**
- 8 threads x 40,000 concurrent `cat('a','b')` aborts with `free(): double free detected in tcache 2` (rc 134) on both HEAD and base; mixed cat/mul/total also aborts on both (HEAD double free, base stack smashing). This is shared typed-clone cleanup/arena state, not the changed jmp/savep.
- `_analysis` hangs (>20 s) on a function with two list parameters each iterated; same on base.
- `list[float]` parameters and positional-only/keyword-only functions produce no mix unit; same on base.

**Unverified:** typedpar/parallel-loop overflow under the new thread-local `jmp_buf` (worker-thread longjmp); benchmark timings/icount (no hot compiler/runtime path changed); free-threaded CPython.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2883044, "input": 35379, "output": 14896, "reasoning": 34817, "cache.write": 0, "cache.read": 2797952}]
    tool time: bash 13.8 min
        400s bash   cd /home/runner/work/ail-ci/ail-ci for d in p1 p2 p3 p4 p5 p6 p7 p8; do   f=$(ls /tmp/rprobes/$d/tgt.py /tmp/r
        231s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         60s bash   cd /tmp && for body in "def t(a: list[int], b: list[int]) -> int:\n    s = 0\n    for x in a:\n        s += x\
         40s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 40 python3 - <<'PY' import sys, ast sys.path.insert(
         20s bash   cd /tmp/base/AIL_CURRENT && printf 'def t(a: list[int], b: list[int]) -> int:\n    s = 0\n    for x in a:\n   
         14s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 200 python3 -m unittest -v test_ail_cpython_hybrid 2
          9s bash   sed 's/range(3000)/range(20000)/' /tmp/rprobes/p8/run.py > /tmp/rprobes/p8/run_big.py cd /tmp/rprobes && timeo
          8s bash   cat > /tmp/rprobes/p8/stress2.py <<'PY' import sys, threading sys.path.insert(0, sys.argv[1]); mode = sys.argv

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T14:17:03Z
