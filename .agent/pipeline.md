# job job-std_graphlib-11020038  started 2026-11-01T15:43:38Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done and committed as `16ca428`.

**Result**
- Wrote 12 programs in `lab/stdlib/graphlib/` (15–60 lines each).
- Initial: 0/12 built; all refused with `graphlib.TopologicalSorter (not yet published in NAMES_library.json)`.
- Final: 12/12 build on the general path; all match CPython stdout and exit code on `AIL_IR=0` and `AIL_IR=1`.
- Added `graphlib.TopologicalSorter` / `CycleError` support in `genlib.py` and `prelude_genlib.py`.
- No follow-up feature was needed.

**Probes** (`/tmp/probes/`, both `cmp.sh` builds, all match CPython)
- `g_api.py`, `g_cycles.py`, `g_edges.py`, `g_errors.py`, `g_cycle_matrix.py` (20 generated cycle cases).
- Covered empty/single/duplicate/negative/tuple nodes, argument/list-item/attribute/dict-value nodes, module/from imports and aliases, `graph=`, multiple `done` args, partial `static_order`, self-loops, multiple cycles, and every error path.

**Tests**
- `test_ail_std_graphlib` (new, registered in `tests.d`): OK, 24 builds.
- `test_ail_genlib`: 31 tests OK.
- `test_ail_safetynet`: 5 tests OK.
- `test_ail_files`: 18 tests OK (1 skipped).
- `test_ail_corpus_findings3`: 2 tests OK.
- `test_ail_check`, `test_ail_registry`: OK.
- `tools/update_manifest.py --check`: exit 0.

**Generated C**
- All ten `lab/compare` `main.ail` builds remain byte-identical.
- The `main.py` builds that built before remain identical; the three that fail now failed identically on the pre-change compiler.
[cost $0.0000, opencode tokens {"total": 7185963, "input": 107349, "output": 23364, "reasoning": 18706, "cache.write": 0, "cache.read": 7036544}]
    tool time: bash 24.0 min, write 0.0 min, edit 0.0 min, read 0.0 min
        367s bash   rm -rf /tmp/cmpcall && mkdir -p /tmp/cmpcall && fail=0; for d in lab/compare/src/*; do t=$(basename "$d"); mkd
        245s bash   python3 -B AIL_CURRENT/test_ail_corpus_findings3.py 2>&1 | tail -25
        214s bash   python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -25
        139s bash   python3 -B AIL_CURRENT/test_ail_files.py 2>&1 | tail -25
         87s bash   for t in rail_transfer chain_relax; do d=lab/compare/src/$t; mkdir -p /tmp/cmpcall/$t/new2 /tmp/cmpcall/$t/old
         87s bash   python3 -B AIL_CURRENT/test_ail_std_graphlib.py -v 2>&1 | tail -30
         86s bash   python3 -B AIL_CURRENT/test_ail_genlib.py 2>&1 | tail -25
         83s bash   rm -rf /tmp/cmpail && mkdir -p /tmp/cmpail && fail=0; for d in lab/compare/src/*; do t=$(basename "$d"); mkdir

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** Adds `graphlib.TopologicalSorter` and `CycleError` to the general-path library lowering (`genlib.py` TABLE/KEYWORDS plus a hand-written `prelude_genlib.py` copy of CPython 3.12's `graphlib`), so `import graphlib` programs compile on the general path. Also adds 12 realistic programs, a registered test that compares them with CPython, DEVLOG/RESULTS, and manifest pins. This matches the report.

**Probes** (`/tmp/rprobes/`, `~/tools/cmp.sh`, general + default builds; all matched CPython stdout/exit):

- `p1.py`: DAG with shared descendants/cross edges (false-cycle check), self-loop, 3-cycle, multiple disjoint cycles, ready/active after `CycleError` — OK.
- `p2.py`: int/tuple/None/empty-string/negative nodes; nodes via dict value, attribute, list item, function argument — OK.
- `p3.py`: partial `static_order` generator, second `static_order`, `done(*ready)`, empty `done`, `is_active` — OK.
- `p4.py`: `import graphlib` module use, alias, duplicate predecessors, repeated `add`, add-after-prepare — OK.
- `p5.py`: `bool()` before/after prepare, draining a cyclic sorter — OK.
- `p6.py`: unhashable node (`TypeError`), string/None graph values, 500-node chain and deep cycle — OK.
- `p7.py`: `repr(CycleError)`, args, `isinstance`/subclassing, `type.__name__` — OK.
- `p8.py`: mutate the source dict after construction, get_ready tuple type, independent sorters — OK.
- `plain.py` (no graphlib): general+default match; `--debug-dir` `program.c` byte-identical to `/tmp/base`.

**Report claims:**
- 12/12 general path, both `AIL_IR` modes: verified (`test_ail_std_graphlib`, 24 builds).
- Initial 0/12 refused with the stated message: verified on base for `add_edges`.
- Typed path still refuses `import graphlib` by name: verified via `--strict`.
- Ten `lab/compare` generated C byte-identical: verified all ten against `/tmp/base`.
- `update_manifest.py --check` exit 0: verified.
- Tests: `test_ail_std_graphlib` OK, `test_ail_safetynet` OK, `test_ail_genlib` OK (re-run on HEAD).

**Pre-existing (not caused):** general path refuses `issubclass` and other unsupported builtins; base refuses graphlib by design. No `icount` run needed because non-feature generated C is unchanged.

**Unverified:** the other 11 initial refusals were not individually rerun on base; `TopologicalSorter[T]`, `graphlib.__all__`, pickling/docstrings outside the task scope and not modeled (noted in RESULTS).

VERDICT: ACCEPT
[cost $0.0140, opencode tokens {"total": 475194, "input": 37647, "output": 5081, "reasoning": 6738, "cache.write": 0, "cache.read": 425728}]
    tool time: bash 8.0 min
        221s bash   cd /home/runner/work/ail-ci/ail-ci; date; python3 tools/par_check.py -j 2 test_ail_std_graphlib test_ail_safet
         88s bash   cd /home/runner/work/ail-ci/ail-ci; date; python3 tools/par_check.py -j 2 test_ail_genlib 2>&1 | tail -10
         46s bash   cd /home/runner/work/ail-ci/ail-ci; for t in echo_pack ledger_bin rail_transfer scar_life term_rank ticket_aud
         42s bash   cd /home/runner/work/ail-ci/ail-ci; rm -rf /tmp/cdiff; mkdir -p /tmp/cdiff; for t in berth_sim chain_relax tre
         35s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p1.py /tmp/rprobes/p2.py /tmp/rprobes/p3.py /tmp/rpr
         19s bash   cd /home/runner/work/ail-ci/ail-ci; cat > /tmp/rprobes/plain.py <<'EOF' import json, collections, heapq d = {"
         11s bash   cd /home/runner/work/ail-ci/ail-ci; cat > /tmp/rprobes/p8.py <<'EOF' from graphlib import TopologicalSorter  g
          9s bash   cd /tmp/base && git log --oneline -1; cd /home/runner/work/ail-ci/ail-ci; cat > /tmp/rprobes/p6.py <<'EOF' fro

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T17:38:18Z
