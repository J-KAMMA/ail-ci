# job job-rbprog14-11021836  started 2026-11-02T09:40:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `d4cea8c` on `job-rbprog14-11021836`.

- Re-applied prog14 changes across hybrid, pymix, pyboxed2, pyfunc, DEVLOG, manifest, and new prog14 test/doc files.
- `test_ail_prog14`: 6 passed; targeted modules + required tests: 86 passed, 1 skipped.
- Probes `p14_annotated`, `p14_constants`, `p14_range`, `p14_tuple`: all matched CPython on both `g` and `d` builds.
- `update_manifest.py --check`: passed. `tools/diff_ids.py` does not exist in this tree.
[cost $0.0000, opencode tokens {"total": 3804480, "input": 173362, "output": 17367, "reasoning": 9655, "cache.write": 0, "cache.read": 3604096}]
    tool time: bash 15.5 min
        880s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3000 python3 -m unittest test_ail_cpython_hybrid tes
         25s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 -m unittest -v test_ail_prog14 2>&1 | t
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p14_*.py; do echo "===== $p"; bash ~/tools/cmp.sh "
          7s bash   cd /home/runner/work/ail-ci/ail-ci && git fetch https://github.com/J-KAMMA/ail-ci.git job-prog14-11021358 2>&1
          1s bash   cd /home/runner/work/ail-ci/ail-ci && ls lab/census/programs/gdev/g02_002.py lab/corpus/programs/glm-5.3-flash
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_prog14.py AIL_CURRENT/tests.d/test_ail_prog
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/diff_ids.py 2>&1 | tail -20; echo "diff_ids rc=$?"; python
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -5 && ls

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review: re-apply prog14 (`d4cea8c`)

**What the change does.** It re-applies the accepted prog14 patch: `pymix` infers tuple/annotated assignments and keeps one-time literal/annotated module constants in the candidacy slice; `pyboxed2` keeps those constants in the mixed-mode slice; `pyfunc` accepts annotated module constants and fixes `len(range(...))`; the hybrid body gate proves nonzero divisors (literal/local/module constant) and permits builtin `range`/`len`. The 26 extra hybrid lines vs. the fetched patch are the newer base's str/list `_safe_call` gates kept alongside the new proofs (a `_safe_builtin_name` refactor), not a semantic divergence. Base already contained the equivalent `test_ail_cpython_hybrid` expectations.

**Probes** (all `/tmp/rprobes`, both `g`/`d` builds via `cmp.sh`; hybrid builds separately):
- `p_ann`, `p_ann_late`, `p_ann_dup`, `p_ann_global`, `p_annot_local` – annotated int/list/bool/negative, late, duplicate and `global` rebinding: CPython match; only the expected helpers accelerated.
- `p_div`, `p_float_div` – positive/negative local and module divisors, parameter/zero/bool/float divisors: match, including `ZeroDivisionError`.
- `p_range_len`, `p_range_zero` – negative/zero bounds, 3-arg and negative step, `a>b`, zero step, bool bound: match; zero-step helper stays unaccelerated.
- `p_tuple`, `p_shadow`, `p_globals`, `p_listmut` – simultaneous tuple assignment, shadowed `range`/`len`, dynamic globals/list mutation: match; unsafe cases unaccelerated.
- Worker probes `p14_annotated/constants/range/tuple`: rerun, all match.

**Tests** (`par_check.py -j 2`): `test_ail_prog14`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (test_ail_prog14 has 6 tests). `update_manifest.py --check` passes; `tools/diff_ids.py` is absent as reported.

**Unchanged programs:** generated `program.c` is byte-identical to `/tmp/base` for `p_plain.py`, `g00_000`, `g02_002`.

**Pre-existing:** none observed.

**Unverified:** instruction-count timing (`perf_event_open` is permission-denied here, so `tools/icount` cannot run); the exact “86 passed, 1 skipped” aggregate (modules pass, counts not reproduced); the wider suite was not run by design.

**Claims:** re-application scope, test passes, probes, manifest check and missing `diff_ids.py` all verified; commit trailer present.

VERDICT: ACCEPT
[cost $0.0326, opencode tokens {"total": 1904611, "input": 82589, "output": 8330, "reasoning": 16316, "cache.write": 0, "cache.read": 1797376}]
    tool time: bash 7.7 min
        380s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_prog14 test_ail_cpy
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "########## $(basename $p)"; timeout
         21s bash   cd /tmp && for p in p_ann p_ann_late p_ann_dup p_ann_global p_div p_float_div p_range_len p_range_zero p_tuple
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p14_*.py; do echo "## $(basename $p)"; timeout 300 
          8s bash   cd /tmp && for prog in /home/runner/corpus/gdev/g00_000.py /home/runner/corpus/gdev/g02_002.py; do n=$(basenam
          5s bash   cd /tmp/rprobes && cat > p_listmut.py <<'EOF' PLAIN = [1, 2, 3] ANNOT: list = [10, 20]   def count_plain() -> 
          2s bash   cd /tmp/rprobes && cat > p_globals.py <<'EOF' PLAIN = 7 ANNOT: int = 11   def fp(n: int) -> int:     return n 
          2s bash   cd /tmp && rm -rf /tmp/cmphead /tmp/cmpbase /tmp/dbg_head /tmp/dbg_base && mkdir -p /tmp/cmphead /tmp/cmpbase 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T11:27:37Z
