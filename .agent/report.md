# job job-ctimeprofb-11040508  started 2026-11-03T20:09:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done on `job-ctimeprofb-11040508` (commits `39075ed5`, `cf55b0b7`); not pushed per the runner rule.

- Fixed `lab/profile/run.py`: cold/warm now share `AIL_FE_CACHE_DIR`, the hit is asserted from `AIL_FE_CACHE_LOG`, and child bytecode is no longer suppressed. Old raw data was all `miss`.
- Added `lab/profile/CTIME_2026-11.md`: 10/10 task phase tables, cold/hit timings, hit top-10, next cuts. Chain_relax cold **1.81 s**, hit **0.82 s** (target ≤1.5 s); the old 3.99 s “hit” was a miss plus no-bytecode imports.
- No code cut: remaining hit cost is `_load_sources`/module imports and gcc, outside the allowed files, so the .md ends with measured next cuts. No `program.c` changed.

Tests: `test_ail_fe_cache`, `test_ail_files`, `test_ail_corpus_findings3` pass; `test_ail_safetynet` passes without `ulimit -v` (the known `S4_generators_gc` failure is the 1.5 GB cap). `update_manifest.py --check` passes. The 20 CI shards were not run because pushing is disabled here.
[cost $0.0000, opencode tokens {"total": 4379343, "input": 105051, "output": 24448, "reasoning": 28148, "cache.write": 0, "cache.read": 4221696}]
    tool time: bash 15.6 min, write 0.0 min
        414s bash   cd /home/runner/work/ail-ci/ail-ci && (ulimit -v 1500000; timeout 1700 python3 lab/profile/run.py --runs 3 --o
        281s bash   cd /home/runner/work/ail-ci/ail-ci && (ulimit -v 1500000; timeout 1200 python3 tools/par_check.py -j 2 test_ai
        154s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 1 test_ail_safetynet 2>&1 | ta
         43s bash   git fetch origin --prune 2>&1 | tail -20; echo "---"; git branch -r | head -50
         18s bash   cd /home/runner/work/ail-ci/ail-ci && sed -i "s/AIL_CHILD_TIME/AILPROF_CHILD_TIME/g; s/AIL_PARENT_TIME/AILPROF
          9s bash   cd /home/runner/work/ail-ci/ail-ci && sed -i '18a from pathlib import Path' lab/profile/run.py && timeout 360 
          8s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 300 python3 lab/profile/run.py --tasks chain_relax --runs 1 --no
          7s bash   cd /home/runner/work/ail-ci/ail-ci && sed -i "s/PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', AIL_SERVER='0'/PY

## review 0 failed to run: (free quota used up; paid model from here) [model commandcode/deepseek-v4.1-flash] 

## review 0
[model commandcode/deepseek-v4.1-flash]

FINAL VERDICT: ERROR  2026-11-03T21:05:03Z
