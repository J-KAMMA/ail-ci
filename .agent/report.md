# job job-arena1s2c-11041356  started 2026-11-04T04:56:57Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining review defect.

**Defect:** `global`/`nonlocal` alias stores were elided because the declaration check only scanned the alias's live range.

**Fix:** `_elide_readonly_field_alias_in_function` now collects `Global`/`Nonlocal` names function-wide and refuses elision when either the alias or its owner is declared outer (`pyfunc.py`).

**Probes** (default + `AIL_UNIFIED_FORCE=1`, all match CPython):
- `p10_global.py` — review reproducer (`2\n2` now)
- `p10b_global_owner.py`, `p10c_nonlocal.py`, `p10d_global_read.py`
- `p10e_normal.py` — normal shape still elides `f_nm`/`f_par`

**Tests** (`-j 2`, 0 failed):
- `test_ail_readonly_field_alias` — added `test_global_and_nonlocal_aliases_match_cpython`
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`

Manifest updated and `--check` clean. Committed as `599b6e9`.
[cost $0.0000, opencode tokens {"total": 1376875, "input": 43951, "output": 5779, "reasoning": 4521, "cache.write": 0, "cache.read": 1322624}]
    tool time: bash 3.7 min, edit 0.0 min
        200s bash   python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | tail -40
         11s bash   python3 tools/par_check.py -j 2 test_ail_readonly_field_alias 2>&1 | tail -30
         10s bash   for p in /tmp/probes/p10*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" "$PWD"; done 2>&1 | tail -80
          2s bash   d=$(mktemp -d); cp /tmp/probes/p10_global.py $d/p.ail; cd $d; python3 /home/runner/work/ail-ci/ail-ci/AIL_CURR
          1s bash   d=$(mktemp -d); cp /tmp/probes/p10_global.py $d/p.ail; cd $d; python3 /home/runner/work/ail-ci/ail-ci/AIL_CURR
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && echo MANIFEST_OK && git status
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && echo MANIFEST_OK
          0s bash   python3 tools/par_check.py -j 2 test_ail_readonly_field_alias 2>&1 | tail -30

## review 0
[model opencode/deepseek-v4.1-flash-free]
## What the change really does

Adds a function-wide `Global`/`Nonlocal` scan to `_elide_readonly_field_alias_in_function` (`pyfunc.py`) and refuses the alias elision when either the alias name or its owner is declared outer. This matches the worker's report.

## Probes (`bash ~/tools/cmp.sh <p> $PWD`, default + forced; base = `/tmp/base` at `work`)

| probe | HEAD | base | note |
|---|---|---|---|
| p10_global (review reproducer) | same `2\n2` | **DIFF** `2\n1` | defect reproduced on base, fixed on HEAD |
| p10c_nonlocal | same | same | nonlocal alias |
| p10e_normal | same | same | still elides `f_nm`/`f_par` (direct field reads, no snapshots) |
| p10f_global_mutate | same | same | global alias then append |
| p10g_global_read_nested | same | same | nested reader of global alias |
| p10h_unrelated_global | same | same | unrelated `global` does not disable elision |
| p10i_listitem_owner | same | same | owner through a list item keeps copy |
| p10j_plain | same | same | generated `program.c` **byte-identical** to base |
| p10k_global_writeonly | same | same | store-only global alias kept |
| p10l_global_sortkey | same | same | global alias + sort-key lambda |

`tree_fold`: generated C byte-identical to base; binary sha256 `9dcb9ce4…` on both, so the hot benchmark is untouched.

## Tests

`test_ail_readonly_field_alias`, `test_ail_safetynet` at `-j 2`: 0 failed (133 s). `update_manifest.py --check`: clean.

## Claims

1. Function-wide `Global`/`Nonlocal` collection, refuse alias/owner outer — **verified** (diff + probes).
2. `p10_global` now `2\n2` — **verified**.
3. Worker probe files `p10b`–`p10e` — **unverified exactly** (not in tree); equivalent shapes p10c/e/f/g/h/k/l pass.
4. Normal shape still elides — **verified**.
5. New test runs default and forced builds — **verified** (module passes).
6. Four test modules 0 failed — **partially verified** (changed module + safetynet only, per review scope).
7. Manifest updated/clean — **verified**.
8. Commit `599b6e9` — **verified**.

No pre-existing differences found. Unverified: `test_ail_files`, `test_ail_corpus_findings3`, ASan/UBSan, full RSS/wall rerun (tree_fold C/binary are identical to base, so unaffected).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 836900, "input": 25231, "output": 5582, "reasoning": 7111, "cache.write": 0, "cache.read": 798976}]
    tool time: bash 2.9 min
        134s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_readonly_field_alias test_ail_safetynet 2>
         17s bash   date; for p in /tmp/rprobes/*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E
          6s bash   cat > /tmp/rprobes/p10k_global_writeonly.py <<'EOF' class T:     nm: list[str]     par: list[int]     def __in
          5s bash   date; for p in /tmp/rprobes/p10_global.py /tmp/rprobes/p10e_normal.py; do echo "=== base $(basename $p)"; bash
          4s bash   d=$(mktemp -d); AIL_NO_CACHE=1 python3 AIL_CURRENT/ailc.py lab/compare/src/tree_fold/main.ail -o $d/tf --debug
          4s bash   d=$(mktemp -d); AIL_NO_CACHE=1 python3 /tmp/base/AIL_CURRENT/ailc.py lab/compare/src/tree_fold/main.ail -o $d/
          2s bash   d1=$(mktemp -d); d2=$(mktemp -d); cp /tmp/rprobes/p10e_normal.py $d1/p.ail; cp /tmp/rprobes/p10e_normal.py $d2
          1s bash   date; bash ~/tools/cmp.sh /tmp/rprobes/p10_global.py /tmp/base 2>&1 | sed -n '1,20p'

## full suite
test_ail_ir_cover

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed `test_ail_ir_cover`: the read-only alias pass was eliding field borrows owned by struct locals, hiding IR `field_borrows`. It now only elides parameter-owned aliases, restoring `field_borrows == 2`.

Verified:
- `test_ail_ir_cover` — 5 tests OK
- `test_ail_readonly_field_alias` — 4 tests OK
- `test_ail_ir_s3b` — 14 OK
- `test_ail_ir_f1` — 13 OK
- Manifest check clean

Committed as `2b4aa0f`.
[cost $0.0000, opencode tokens {"total": 1136973, "input": 47017, "output": 3547, "reasoning": 4425, "cache.write": 0, "cache.read": 1081984}]
    tool time: bash 4.0 min
        168s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_ir_s3b 2>&1 | tail -30
         19s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_ir_f1 2>&1 | tail -30
         17s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_ir_cover 2>&1 | tail -40
         16s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_ir_cover 2>&1 | tail -80
         11s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_readonly_field_alias 2>&1 | tail -60
          2s bash   cd AIL_CURRENT && python3 - <<'PY' from pathlib import Path p=Path('python/pkg-v12/pyfunc.py') s=p.read_text()
          2s bash   cd AIL_CURRENT && cp python/pkg-v12/pyfunc.py /tmp/pyfunc.head.py && git show HEAD~1:AIL_CURRENT/python/pkg-v1
          2s bash   cd AIL_CURRENT && python3 - <<'PY' import tempfile, json, sys, os from pathlib import Path import test_ail_ir_

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T07:43:37Z
