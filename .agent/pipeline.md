# job job-rbnoimpl-11011913  started 2026-11-01T10:15:46Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed (`ef5b714`).

**Cause:** strict `-Werror=implicit-function-declaration` rejected the v1 runtime's `calloc`/`malloc`/`free` because its DIE block preceded the `<stdlib.h>` include. The pipeline then silently rebuilt through the unified fallback, which broke `test_ail_pre246` and made v1 exact-int `10**40` print instead of stopping (`test_ail_pre33`).

**Fix:** `pyboxed.py` v1 preamble now includes `<stdlib.h>` before the `OBJ` fragment; added `test_v1_general_runtime_declares_stdlib` (asserts no `program-2.c` fallback).

**Probes** (`cmp.sh`, both g/d builds; also `AIL_GENERAL=v1`, no fallback):
- `p_v1_alloc`, `p_v1_args`, `p_v1_empty`, `p_v1_negative` — all match CPython on both builds and v1.

**Final-commit tests** (par_check `-j 2`): 6/6 pass — `test_ail_pre246`, `test_ail_pre33`, `test_ail_no_implicit_decl`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. `update_manifest.py --check` exits 0. No new module or DIFFERENCES row.
[cost $0.0000, opencode tokens {"total": 5882963, "input": 206960, "output": 10543, "reasoning": 15156, "cache.write": 0, "cache.read": 5650304}]
    tool time: bash 13.6 min
        466s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre246 test_ail_pre33 test_ail_
        138s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_pre246 test_ail_pre33 test_a
         64s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre33 2>&1 | tail -60
         50s bash   cd /tmp/base/AIL_CURRENT && python3 -m unittest -q test_ail_pre33 2>&1 | tail -25
         36s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre246 2>&1 | tail -60
         27s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_v1_alloc.py <<'PY' class Box:     def __init__(self, v):         s
         14s bash   cat > /tmp/probes/p_v1_alloc.py <<'PY' class Box:     def __init__(self, v):         self.v = v  def show(x): 
          6s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 180 git fetch --no-tags origin integ:refs/remotes/origin/integ j

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review**

Diff really does: adds `#include <stdlib.h>` to the v1 (`AIL_GENERAL=v1`, `pyboxed.py`) C preamble so the DIE block's `calloc`/`malloc`/`free` are declared before use; adds one regression test; updates manifest hashes and DEVLOG. No compiler/runtime semantics changed outside v1.

**Probes** (own, `/tmp/rprobes`; `cmp.sh` g/d, plus explicit `AIL_GENERAL=v1` on HEAD and on `work`=419aae1)
- `p_alloc` (list/dict/class/attribute): g/d match CPython; v1 build 0, only `program.c`, matches. On work v1 fails with implicit `malloc`/`calloc`.
- `p_exc` (try/except, ValueError, ZeroDivisionError): g/d match; v1 build 0, no fallback, matches. Same failure on work.
- `p_empty` (empty list/dict, then append/insert): g/d and v1 match.
- `p_neg` (negative ints, dict, indexing): g/d and v1 both replicate CPython's `KeyError: -3`, exit 1.
- `p_bigpow` (`x = 10 ** 40`): g/d refuse by name (`int64 constant ... outside ...`), accepted. With `AIL_EXACT_INT=1`, HEAD v1 builds `program.c` only, run exits 1 with `OverflowError`, empty stdout; work v1 falls back (`program-2.c`) and prints the exact 41-digit value — the bug the fix targets.
- Default (non-v1) `program.c` byte-identical HEAD vs work for `p_alloc`/`p_exc`, so programs not using v1 are unchanged.

**Tests on HEAD** (`par_check -j 2`): 6/6 pass — `test_ail_pre246`, `test_ail_pre33`, `test_ail_no_implicit_decl`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. `update_manifest.py --check` exits 0. Only the three v1-using modules exist, so no other test paths are affected.

**Report claims** — verified: cause (DIE before `<stdlib.h>` rejected by strict flags), silent fallback in exact-int mode, fix, added test. The one nuance: a plain v1 build on `work` fails outright (exit 4) rather than falling back; fallback occurs in exact-int mode (`AIL_EXACT_INT=1`), which is precisely the `test_ail_pre33` failure. Not a defect in the fix.

**Pre-existing:** none relevant; the only C difference is the intended include (v1) and default C is unchanged. **Unverified:** wider suite (per instructions) and speed (header-only change, no runtime effect).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1275942, "input": 56977, "output": 6443, "reasoning": 10090, "cache.write": 0, "cache.read": 1202432}]
    tool time: bash 7.6 min
        361s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre246 test_ail_pre33 tes
         60s bash   date; cd /tmp/basework && python3 tools/par_check.py -j 2 test_ail_pre246 test_ail_pre33 2>&1 | tail -60
         15s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh 
          8s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p_alloc.py /tmp/rprobes/p_exc.py; do n=$(basen
          3s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/*.py; do n=$(basename "$p" .py); d=/tmp/v1_$n;
          3s bash   date; for tree in /tmp/basework /home/runner/work/ail-ci/ail-ci; do tag=$(basename $tree); d=/tmp/ex_${tag}; r
          1s bash   date; cd /tmp/basework; for p in /tmp/rprobes/p_alloc.py /tmp/rprobes/p_exc.py; do n=$(basename "$p" .py); d=/
          1s bash   date; cd /tmp/base; for p in /tmp/rprobes/p_alloc.py /tmp/rprobes/p_bigpow.py; do n=$(basename "$p" .py); d=/t

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T12:02:06Z
