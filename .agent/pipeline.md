# job job-rbprog29-11022318  started 2026-11-02T14:25:09Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied the accepted prog29 change on top of this tree, kept both sides of the conflicts, and committed as `5385a90`.

- Files: 11 changed (+906/−12), including `pyc.py`, `pyfunc.py`, `test_ail_prog29.py`, `tests.d/test_ail_prog29.txt`, both DEVLOGs, `lab/progfix/prog29.md`, and regenerated manifest shards.
- `python3 tools/update_manifest.py` and `--check`: pass.
- `tools/diff_ids.py`: absent from this tree (consistent with prior DEVLOG notes), so it could not be run.

Tests on the final commit:
- `test_ail_prog29`: 13 passed (40s)
- `test_ail_safetynet`: 5 passed (170s)
- `test_ail_files`: 18 passed, 1 skipped (15s)
- `test_ail_corpus_findings3`: 2 passed (41s)

Probes (`bash ~/tools/cmp.sh`, both `g` and `d` builds; all matched CPython):
- `prog29b_setcomp.py`: argument, list item, attribute, dict value, empty, duplicates, negative ints — same.
- `prog29b_frozenset.py`: string/list literals, duplicates, empty, non-ASCII, `in`/`not in`/`len`, values via argument/list item/attribute/dict — same.
- `prog29b_mutate_list.py`: CPython `3 3`, default/general same.
- `prog29b_mutate_set.py`: CPython `RuntimeError`/exit 1, default/general same.
- `prog29b_shadow_inner.py`: inner-only `len` shadow, same.
- `prog29b_shadow_len.py`: CPython `TypeError`/exit 1, default/general same; `--strict` refuses by name (`not the builtin`).
- `prog29b_before.py`: CPython `NameError`/exit 1, default/general same; `--strict` refuses by name.
- `prog29b_after.py`: typed read-after-assignment, same.
- `prog29b_float.py`: default/general same; `--strict` refuses by name.
- Mutation probes `prog29b_mutate_list.py` and `prog29b_mutate_set.py` are refused by name under `--strict`; `prog29b_float.py` too.
[cost $0.0000, opencode tokens {"total": 1965829, "input": 168208, "output": 6554, "reasoning": 5467, "cache.write": 0, "cache.read": 1785600}]
    tool time: bash 9.8 min
        335s bash   printf '%s\n' test_ail_safetynet test_ail_files test_ail_corpus_findings3 | xargs -P2 -I{} sh -c 'python3 -m u
        170s bash   printf '%s\n' test_ail_prog29 test_ail_safetynet test_ail_files test_ail_corpus_findings3 | xargs -P2 -I{} sh 
         42s bash   python3 -m unittest -v test_ail_prog29 2>&1 | tail -60
         26s bash   for p in /tmp/probes/prog29b_*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | sed 
          8s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-prog29-11022055 && git rev-parse FETCH_HEAD
          2s bash   for p in prog29b_float prog29b_shadow_len prog29b_before prog29b_mutate_list prog29b_mutate_set; do echo "====
          1s bash   cd AIL_CURRENT && python3 -c "import ast; ast.parse(open('python/pkg-v12/pyfunc.py').read()); ast.parse(open('
          1s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo status:$?; git status --sho

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review report**

**What the change really does.** It is a faithful re-application of the accepted prog29 diff: comparing `git diff f5926ab..FETCH_HEAD` with `git diff work..HEAD` for `pyc.py`/`pyfunc.py` shows only hunk line offsets, no content change. It adds module `frozenset(<str literal>)` constants held as ordered de-duplicated `list[str]` (reads restricted to `in`/`not in`/builtin `len`), `len({...})` lowering via a temporary list + private `iset`/`sset` table, a guard for comprehensions over mutable/typed containers whose element/filter runs code, shadowed-`len` refusal, and a read-before-assignment refusal. This matches the report.

**Probes** (all under `/tmp/rprobes`, `--strict` where noted; `cmp.sh` g+d otherwise):
- `a2_setcomp_clean`, `g_setcomp_expr`, `h_setcomp_str_unicode`, `i_setcomp_range_edge`, `o_setcomp_bool`, `b2_setcomp_sources`: typed build, stdout matches CPython (argument, list item, attribute, dict value, slices, range, set source, empty, duplicates, negatives, bool, bool/str/int elements, unicode).
- `c_mutate_local`, `k_setcomp_mutate_setfield`: refused by name under `--strict`; default build matches CPython (mutation during iteration).
- `c_mutate_param`, `p_setcomp_floatlist_int`, `q_setcomp_str_call`, `x_sets_dicts`: conservative by-name refusals; default matches CPython.
- `d2_frozen_clean`: typed build matches CPython (`Final[frozenset[str]]`, unannotated, list arg, empty, duplicates, non-ASCII, `in`/`not in`/`len`, and reads via argument, list item, attribute, dict value).
- `e_frozen_order_class`, `j_frozen_read_before_call`, `l_classbody_order`, `m_defaultarg_order`: read-before-assignment refused by name, matching CPython's `NameError`.
- `f_frozen_alias`, `r_ann_int`, `s_ann_str`, `t_ann_frozen_int`, `v/w_shadow_frozenset_*`: named refusals or matching output.
- Non-feature `plain.py`, `plain2.py`: `--debug-dir` generated `program.c` byte-identical to `/tmp/base` (`native_report.json` differs only in temp paths).

**Tests / records.** `test_ail_prog29` (13 tests) and `test_ail_safetynet` pass; `test_ail_files` and `test_ail_corpus_findings3` also pass (all with `-j 2`). `update_manifest.py --check` passes; `tools/diff_ids.py` is absent. Manifest shards and `tests.d/test_ail_prog29.txt` are correct.

**Pre-existing.** `u_forlen_module.py` (module-level `for len in [5]`) prints `5` at exit 0 instead of CPython's `TypeError`; the base worktree gives the identical result on both builds, so it is not caused by this change. Direct typed-dict/set-of-str iteration and tuple-source comprehensions are also refused on base.

**Unverified.** Instruction counts could not be measured (`perf_event_open: Permission denied`); only two non-feature programs were C-diffed, not all ten `lab/compare` tasks.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2023262, "input": 137634, "output": 12273, "reasoning": 20299, "cache.write": 0, "cache.read": 1853056}]
    tool time: bash 7.8 min
        231s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test
        170s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog29 tes
         33s bash   date; cd /tmp/rprobes; WT=/home/runner/work/ail-ci/ail-ci; for p in a_setcomp_routes b_setcomp_sources c_mutat
          6s bash   cd /tmp/rprobes && cat > u_forlen_module.py <<'EOF' V = frozenset("aeiou") for len in [5]:     pass print(len(
          5s bash   cd /tmp/rprobes && rm -rf /tmp/dbgX && mkdir -p /tmp/dbgX; date; AIL_NO_CACHE=1 python3 /home/runner/work/ail-
          4s bash   date; cd /tmp/rprobes; WT=/home/runner/work/ail-ci/ail-ci; for p in a_setcomp_routes b_setcomp_sources c_mutat
          3s bash   cd /tmp/rprobes && cat > a2_setcomp_clean.py <<'EOF' class Box:     def __init__(self, xs: list[int]) -> None:
          3s bash   date; cd /tmp && cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount /home/runner/work/ail-ci/ail-ci/

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T16:05:10Z
