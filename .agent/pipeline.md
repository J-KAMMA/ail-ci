# job job-prog20-11021017  started 2026-11-02T01:25:28Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `f1a0b52` on `job-prog20-11021017`.

**Result**
- Profiled all 8 programs; profiles and first refusals in `lab/progfix/prog20.md`.
- Whole-program typed after: `g05_006`, `g18_002`, `t206` (was already) — **3/8**.
- Hot functions typed: **5/18** after vs **1/18** before.
- Compiler changes:
  - `iterlower.py`: tuple-key `min`/`max`, lexicographic fields, dict and sequence sources.
  - `pyfunc.py`: nested tuple target in `enumerate(rows, start)` over tuple-instance lists and `srowtypes`.
- Remaining 5 programs are named follow-ups: `g03_012`, `g03_028`, `t284`, `g25_002`, `g14_012`.

**Probes** — all matched CPython on both `cmp.sh` builds and took the typed path:
- `/tmp/probes/p_tuplekey.py`
- `/tmp/probes/p_enum_tuple.py`
- `/tmp/probes/p_enum_append.py`

**Tests** — 64 passed, 1 skipped (missing zig):
`test_ail_prog20`, `test_ail_tuples`, `test_ail_bugs7`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

**Regression** — generated `program.c` byte-identical to `HEAD` for all 10 `lab/compare` `main.ail` builds and every `main.py` build that builds on both. `update_manifest.py --check` passes.
[cost $0.1132, opencode tokens {"total": 13034429, "input": 222893, "output": 35481, "reasoning": 33783, "cache.write": 0, "cache.read": 12742272}]
    tool time: bash 46.3 min
        812s bash   cd /home/runner/work/_temp/w2 && AIL_CC_JOBS=2 AIL_FE_JOBS=2 python3 -m unittest -v AIL_CURRENT.test_ail_prog2
        421s bash   cd /home/runner/work/_temp/w2 && AIL_CC_JOBS=2 AIL_FE_JOBS=2 python3 -m unittest AIL_CURRENT.test_ail_prog20 A
        381s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/compare_c20.py <<'PY' import concurrent.futures, os, pathlib, shut
        104s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/census_direct.py <<'PY' import sys,json,os sys.path.insert(0,'lab/
         87s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/comp20 && for f in lab/census/programs/gdev/g03_012.py lab/cens
         81s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import pathlib p=pathlib.Path('AIL_CURRENT/python/pkg-v12/py
         79s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/base20 && mkdir -p /tmp/base20 && git archive HEAD | tar -x -C /t
         77s bash   cd /home/runner/work/_temp/w2 && cp AIL_CURRENT/python/pkg-v12/pyfunc.py /tmp/pyfunc_save.py && python3 - <<'P

## review 0
[model opencode-go/deepseek-v4.1-flash]
Review complete.

**What the change does (one line):** `iterlower.py` lowers `min`/`max` with a tuple-returning lambda key by comparing fields lexicographically (dict and sequence/range/str sources), and `pyfunc.py` accepts a nested `(i, (a, b))` target for `enumerate(..., start)` over tuple-instance lists and `srowtypes` row lists.

**Probes** (all typed, both `cmp.sh` builds matched CPython):
- `/tmp/rprobes/p1d.py` dict tuple key: ties, negatives, 3 fields, int keys, default empty/non-empty, value via dict item, list item and argument.
- `/tmp/rprobes/p2d.py` list/range/float/str tuple keys, empty + default, empty no default (`ValueError`).
- `/tmp/rprobes/p3_enum_olist.py`, `p19_nostart.py` nested enumerate: start 1/0/-3/near-int64, empty, rebound index/start, no-start.
- `/tmp/rprobes/p4_enum_srow.py`, `p7c_srow3.py`, `p9_enum3.py` `srowtypes` and 3-field mixed str/int/float rows (positional mapping, body rebinding fields).
- `/tmp/rprobes/p5_mutate.py`, `p16_srow_append.py`, `p13/p14` append or rebind the source during iteration — matched.
- Refusals/fallbacks, still CPython-correct: name collision (`p10/p11`), nested tuple key (`p12`), shadowing the source (`p17/p18`).
- Worker probes `p_tuplekey`, `p_enum_tuple`, `p_enum_append`: typed and matched.

**Tests:** `test_ail_prog20` ok (14.4s), `test_ail_safetynet` ok (177.4s). `update_manifest.py --check` passes.

**Regression:** `program.c` byte-identical to `work` for all 10 `lab/compare/src/*/main.ail` builds.

**Claims:** Change matches report. Verified: 3/8 programs typed after vs 1 before (`g05_006`, `g18_002`, `t206`), exact first refusals for the other five, 5/18 hot functions, probes typed, all 10 compare C files unchanged. Unverified: exact 64-passed count for the four extra modules; `main.py` byte-identity; speed (perf_event_open denied on runner).

**Pre-existing, non-blocking:** tuple-key `min`/`max` written directly inside another call, or over a tuple source, still falls back to the general path (also true on `work`).

VERDICT: ACCEPT
[cost $0.0494, opencode tokens {"total": 2930876, "input": 109759, "output": 13873, "reasoning": 27084, "cache.write": 0, "cache.read": 2780160}]
    tool time: bash 10.0 min
        179s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_
         84s bash   cd /home/runner/work/_temp/w2; date; fail=0; for t in $(ls lab/compare/src); do for side in head base; do wt=$
         66s bash   cd /home/runner/work/_temp/w2; cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c 2>&
         53s bash   ls -l /tmp/probes/p_tuplekey.py /tmp/probes/p_enum_tuple.py /tmp/probes/p_enum_append.py 2>&1; echo ---base-ch
         46s bash   cd /home/runner/work/_temp/w2; date; for f in lab/census/programs/gdev/g03_012.py lab/census/programs/gdev/g03
         41s bash   cd /home/runner/work/_temp/w2; for t in ticket_audit tree_fold berth_sim; do for side in head base; do wt=$PWD
         26s bash   date; for p in p1_dict p2_seq p3_enum_olist p4_enum_srow p5_mutate p6_nofeature; do echo "=== $p"; timeout 300
         17s bash   date; for p in p1d p2d p2a p2b; do echo "=== $p"; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/$p.py $PWD 2>&1

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T06:27:49Z
