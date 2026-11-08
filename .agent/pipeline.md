# job job-fbnarrow3-11081338  started 2026-11-08T04:42:52Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `2c909b5`.

**Defects addressed**
1. `try` frame-cell declarations now use `ail_ilist` for narrowed locals (`pyfunc.py:42863`). `p19_try_for.py` builds and matches CPython in both builds; generated C shows `ail_ilist v_xs`.
2. Manifest refreshed (`update_manifest.py --check` clean); `par_check.py -j 2 test_ail_narrow_int test_ail_safetynet` passes.
3. Tightened the analysis so `tree_fold`'s hot `w`/`dep`/`par` fields and matching locals stay `ail_list` (blocked by `.copy()`, augmented index writes, sort-key/lambda/comprehension bodies, and field→local stores). Instructions now **−1.30%** vs default at N=3000 (8,608,126 vs 8,721,379 via ptrace single-step); RSS 367,320 vs 367,304 KiB. Documented in `lab/mem/NARROW_RESULTS.md`.

**Verification**
- `test_ail_narrow_int`: 9/9 OK; `test_ail_safetynet`: 5/5 OK.
- `test_ail_files`: 18 OK (1 skipped); `test_ail_corpus_findings3`: 2/2 OK.
- 10 compare tasks, 511 public+hidden cases: 0 differences narrow vs default vs `reference.py`.
- Probes `p19_try_for`, `p_field_sort_copy`, `p_local_ops`, `p_field_alias`: all match CPython.
- Default-build `tree_fold` `program.c` byte-identical before/after this change.

Not pushed (per job rules).
[cost $0.0000, opencode tokens {"total": 8303749, "input": 213377, "output": 21615, "reasoning": 35861, "cache.write": 0, "cache.read": 8032896}]
    tool time: bash 35.4 min, edit 0.0 min
        361s bash   cd /tmp/tf && for x in tf_default tf_narrow; do echo -n "$x "; /tmp/icount_ptrace ./$x < /tmp/tree_3000.bin > 
        316s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' p='/tmp/rss10.py' s=open(p).read() s=s.replace("      
        238s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 AIL_CURRENT/test_ail_corpus_findings3.py 2>&1 | tai
        174s bash   cat > /tmp/check10.py <<'EOF' import importlib.util, os, random, subprocess, sys, tempfile from pathlib import
        129s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_narrow_int test_ai
        129s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_narrow_int test_ai
        127s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -25
        102s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 AIL_CURRENT/test_ail_files.py 2>&1 | tail -30

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fbnarrow3 fix (commit `2c909b5`)

**What the change really does.** Adds the missing `ail_ilist` type to the `try`-frame-cell declaration in `pyfunc.py` (1 line), tightens `ir/narrowint.py` (drops `reverse`/`copy`, blocks augmented index writes, field↔local stores and comprehension/lambda bodies), and refreshes the manifest + `NARROW_RESULTS.md`. Matches the report.

**Review-1 defects**
1. **Frame cell** — fixed. `t1_try_for.py` (narrowed local inside `try`, then `for`, index, pop, clear) builds and matches CPython on HEAD; the same probe fails to build on `/tmp/base` (89922b4) with the old `ail_list` cell. Generated C shows `struct { ail_ilist v_xs; ... }` and `ail_ilist * const v_xs = &...`.
2. **Manifest** — fixed. `update_manifest.py --check` clean; both `pyfunc.py` and `narrowint.py` hashes updated.
3. **tree_fold instructions** — fixed. Rebuilt HEAD: narrow 8,607,393 vs default 8,720,646 = **−1.30%** (report: −1.30%), stdout identical. Narrow C narrows only `v_stack/v_ord/v_codes/v_iargs`; `w/dep/par` stay `ail_list`, as documented. RSS no longer improves, but the brief's stop-rule escape names each blocking use, so this is the sanctioned remedy.

**Probes** (`/tmp/rprobes`, HEAD default / HEAD narrow / base narrow vs CPython)
- `t2_try_ops`, `t3_field_ops` (field pop/clear/for), `t4_field_assign`, `t5_local_field`, `t6–t8` aliasing, `t11` del-index, `t12_truth` (field truthiness/`while`), `p26_sources` (dict value, list item, argument): CPython-equal.
- `t13_iter_mut`: local iteration-mutation matches CPython; field iteration-append differs identically on the base.
- Default `program.c` byte-identical HEAD vs base for `p22_local_field.py` and `tree_fold` (sha `1d998161…`).
- Tests: `par_check.py -j 2 test_ail_narrow_int test_ail_safetynet` → 2 modules, 0 failed.

**Claims vs observation**
1. Frame-cell fix — verified. 2. Manifest — verified. 3. −1.30% instructions — verified; the RSS 367,320/367,304 figure is unverified by me. 4. 9/9 narrow-int and 5/5 safetynet — verified; `test_ail_files`/`corpus_findings3` and the 511-case matrix — unverified. 5. Default-C identity — verified on tree_fold and one probe. Probe list — spot-verified. "Not pushed" — true.

**Pre-existing (identical on base, not blocking)**
- Field iteration while appending visits fewer elements than CPython (`t13_iter_mut`); identical on base/default.
- Field→field store copies instead of aliasing (`p21_field_assign`); identical on HEAD/default and base.
- `xs[-1] -= 5` on a plain `ail_list` segfaults on the base default build too (`t14d.py`); unrelated to narrowing (probe's list is not narrowed).
- `del xs[i]` on a narrowed local is not refused even though `del` is outside the task's operation set; output is nevertheless CPython-correct (`t11`).

**Unverified.** tree_fold peak-RSS at N=3M, the nine-task RSS/instruction numbers, the 511-case matrix, `test_ail_files`/`test_ail_corpus_findings3`, and the `AIL_UNIFIED_FORCE=1` path for the new probes.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 4775050, "input": 68859, "output": 14976, "reasoning": 28815, "cache.write": 0, "cache.read": 4662400}]
    tool time: bash 7.8 min
        222s bash   cd /tmp && ( /tmp/icount_ptrace /tmp/tf2_n < /tmp/tree_3000.bin > /tmp/tf2_n.out 2> /tmp/tf2_n.err; echo "n rc
        129s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_a
         17s bash   cd /tmp/rprobes && cat > t6_alias_after.py <<'EOF' class T:     def __init__(self) -> None:         self.w: li
         16s bash   cd /tmp/rprobes && R=/home/runner/work/ail-ci/ail-ci; for p in p19_try_for p20_try_ops p21_field_assign p22_lo
         16s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/tf2_n /tmp/tf2_d && AIL_NARROW_INT=1 AIL_NO_CACHE=1 python3 -
          9s bash   cd /tmp/rprobes && cat > p28_same_attr.py <<'EOF' class A:     def __init__(self) -> None:         self.w: lis
          9s bash   cd /tmp && rm -rf dbgbase dbgh dbgn; mkdir -p /tmp/droot; R=/home/runner/work/ail-ci/ail-ci; B=/tmp/base; expo
          8s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/tfh /tmp/tfb /tmp/tfh_e /tmp/tfb_e; ( AIL_NO_CACHE=1 PYTHONH

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T06:59:53Z
