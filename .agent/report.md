# job job-cov7-10240917  started 2026-10-24T00:18:05Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done, committed as `de00b03` on `job-cov7-10240917`.

**Census:** 510 programs. Refused before: **53**; after: **50**. The top first-line group was `Traceback (most recent call last):` (**3 -> 0**), not a deliberate refusal.

**Fixes**
- `genlib.py`: `functools.partial` rewrite now copies source locations onto both generated lambdas, fixing the `AttributeError: 'Lambda' object has no attribute 'lineno'` crash in `g17_004` / `g17_024`.
- `pyfunc.py`: the typed dispatcher now falls back to the first concrete implementation when an abstract base method was removed as a stub, fixing `KeyError: 'Visitor__visit_directory'` in `g13_036`.

**Tests:** added the positional-partial corpus program to `test_ail_silent6.py` and an abstract-visitor hierarchy to `test_ail_typed_inherit.py`. On the final commit, all 7 targeted/required modules passed:
`test_ail_virtual_dispatch`, `test_ail_silent6`, `test_ail_genlib`, `test_ail_typed_inherit`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

**Probes** (all match CPython on both builds):
- `/tmp/probes/partial_values.py`
- `/tmp/probes/partial_keywords.py`
- `/tmp/probes/abstract_visitors.py`
- `/tmp/probes/abstract_single.py`
- `/tmp/probes/abstract_base_call.py`

`update_manifest.py --check` passes. No push. `.agent/pipeline.md` remains untracked (pre-existing runner file).
[cost $0.0000, opencode tokens {"total": 4900531, "input": 213947, "output": 14712, "reasoning": 12288, "cache.write": 0, "cache.read": 4659584}]
    tool time: bash 50.1 min, write 0.0 min
       1034s bash   cd /tmp && time python3 census.py ~/corpus/gdev /tmp/census_before.json > /tmp/census_before.txt 2>/tmp/census
        858s bash   cd /tmp && python3 census.py ~/corpus/gdev /tmp/census_after.json > /tmp/census_after.txt 2>/tmp/census_after.
        466s bash   python3 tools/par_check.py -j 2 test_ail_virtual_dispatch test_ail_silent6 test_ail_genlib test_ail_typed_inhe
        336s bash   python3 tools/par_check.py -j 2 test_ail_virtual_dispatch test_ail_silent6 test_ail_genlib test_ail_typed_inhe
        120s bash   cd /tmp && nohup python3 census.py ~/corpus/gdev /tmp/census_after.json > /tmp/census_after.txt 2>/tmp/census_
        109s bash   python3 tools/par_check.py -j 2 test_ail_virtual_dispatch test_ail_typed_inherit 2>&1 | tail -50
         22s bash   python3 tools/update_manifest.py --check && for p in /tmp/probes/*.py; do echo "======== ${p##*/}"; bash ~/too
         15s bash   for f in g13_036 g17_004 g17_024; do echo ====== $f; bash ~/tools/cmp.sh ~/corpus/gdev/$f.py $PWD; done

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review report**

- Diff: `de00b03` touches `genlib.py` (locations on partial-rewrite lambdas), `pyfunc.py` (dispatcher representative fallback), tests, DEVLOG, DIFFERENCES, manifest.
- Census re-derived from `/tmp/census_*.json`: 510 programs, refused 53 -> 50. Only `g13_036`, `g17_004`, `g17_024` changed to OK; no program newly refused, no refusal text changed. Traceback group 3 -> 0 is the unique top first-line group (the datetime messages differ after the first line, despite identical display prefixes).
- Changed behaviours probed (all match CPython on both `g` and `d`):
  - partial: `p1_zero_lambda` (zero-bound, lambda, all-bound, alias), `p2_sources` (argument/list item/attribute/dict value, post-creation mutation), `p3_evalorder` (bound-argument evaluation order/count), `p4_defaults` (comprehension, lambda default, partial inside lambda, dict value), `p5_callbacks` (map/filter, empty list).
  - typed dispatch: `a1_base_concrete` (concrete unconstructed base, all children override; base reached via arg/list/dict/attribute), `a2_base_stub_multiple`, `a3_deep` (multi-level stub), `a4_stub_sig` (stub `-> None`, implementations `-> int`), `a5_partial_override` (mixed inherited/overridden methods).
  - Corpus: `g17_004`, `g17_024`, `g13_036` match on both builds.
- Unrelated C unchanged: `g00_000`, `g07_000`, `g20_000`, `g01_014`, `g13_000`, `g13_002` have identical `program.c` vs base. Partial-using `g03_036`/`g11_020` and inheritance `g13_000` also produce byte-identical executables, so instruction counts are unchanged; no hot-code regression.
- Tests on HEAD: `test_ail_silent6`, `test_ail_typed_inherit`, `test_ail_safetynet`, plus `test_ail_genlib`, `test_ail_virtual_dispatch` all pass (`-j 2`). Manifest `--check` passes. Commit/co-author/branch-id conventions observed.
- Claims: census numbers verified; top group verified; both fixes verified by probes and corpus; test list verified; manifest verified.
- Pre-existing: none encountered.
- Unverified: full 510-program census not re-run (used the worker's JSON and re-derived result sets); full suite not run, per instructions.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1911347, "input": 75765, "output": 21903, "reasoning": 943, "cache.write": 0, "cache.read": 1812736}]
    tool time: bash 6.5 min
        165s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_silent6 te
         59s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_genlib tes
         42s bash   date; cd /tmp; rm -rf /tmp/dbghead /tmp/dbgbase; mkdir -p /tmp/dbghead /tmp/dbgbase; for f in g00_000 g07_000 
         34s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/*.py; do echo "======== ${p##*/}"; bash ~/tool
         32s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/probes/*.py ~/corpus/gdev/g17_004.py ~/corpus/gdev/g17
         27s bash   date; cd /tmp; for f in g01_004 g03_036 g11_020; do echo == $f; rm -rf /tmp/dbghead/$f /tmp/dbgbase/$f; AIL_UN
         19s bash   date; cd /tmp; for f in g01_014 g13_000 g13_002; do echo == $f; rm -rf /tmp/dbghead/$f /tmp/dbgbase/$f; AIL_UN
         13s bash   cat > /tmp/rprobes/p1_zero_lambda.py <<'EOF' from functools import partial   def f(a, b):     return a - b   d

FINAL VERDICT: ACCEPT  2026-10-24T01:26:46Z
