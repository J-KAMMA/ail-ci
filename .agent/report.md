# job job-wedge3-11091201  started 2026-11-09T03:05:37Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed on `job-wedge3-11091201` at `eceb4df5` (measurement in `856e381a`), no push.

- Hybrid made 0/191 functions native; 1.045x CPython geomean; all hybrid outputs byte-identical.
- Added `requirements.txt`, verified 3 probes with `cmp.sh` and hybrid builds, wrote DEVLOG and `test_ail_wedge3`.
- Final-commit tests: `test_ail_wedge3`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- Only untracked `.agent/pipeline.md` remains untouched.
[cost $0.0000, opencode tokens {"total": 11247008, "input": 248547, "output": 37566, "reasoning": 48127, "cache.write": 0, "cache.read": 10912768}]
    tool time: bash 22.6 min, edit 0.0 min, write 0.0 min
        348s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_wedge3 test_ail_safetynet test_
        309s bash   mkdir -p /tmp/wedge3 && cd /home/runner/work/ail-ci/ail-ci && WEDGE_CPY=/tmp/wedge3venv/bin/python WEDGE_PYPY=
        304s bash   mkdir -p /tmp/wedge3 && cd /home/runner/work/ail-ci/ail-ci && WEDGE_CPY=/tmp/wedge3venv/bin/python WEDGE_PYPY=
        133s bash   mkdir -p /tmp/wedge3 && cd /home/runner/work/ail-ci/ail-ci && WEDGE_CPY=/tmp/wedge3venv/bin/python WEDGE_PYPY=
         41s bash   cd /home/runner/work/ail-ci/ail-ci/lab/wedge3/workloads; ulimit -v 2500000; PY=/tmp/wedge3venv/bin/python; for
         35s bash   cd /tmp && rm -rf /tmp/wedge3pypy && /opt/hostedtoolcache/PyPy/3.11.17/x64/bin/pypy3 -m venv /tmp/wedge3pypy 2
         33s bash   cd /home/runner/work/ail-ci/ail-ci/lab/wedge3/workloads; ulimit -v 2500000; PY=/tmp/wedge3venv/bin/python; for
         31s bash   cd /tmp && /opt/hostedtoolcache/PyPy/3.10.16/x64/bin/pypy3 -m venv /tmp/wedge3pypy 2>&1 | tail -3 && /tmp/wedg

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `1f0a6e13..eceb4df5`. The change is measurement-only: it adds `lab/wedge3/{measure.py,workloads,requirements.txt,results.json,RESULTS.md}`, plus DEVLOG, `test_ail_wedge3`, `tests.d` and manifest records; no compiler/runtime source changed.

**Verified**
- 0/191 native on plain and observed builds (41+61+7+38+44=191). Fresh `measure.py` runs on networkx/chardet reproduced 0 native and hybrid stdout == CPython.
- Ratios from `results.json`: h/C geomean 1.0446, h/P 1.5507, h/R 2.4149; table arithmetic matches.
- All five CPython and PyPy workload outputs reproduced; hybrid and observed-hybrid outputs match CPython in `results.json`; fresh hybrid runs match for networkx/chardet.
- `ail_observe` + `annotate`: networkx/jsonschema/difflib change; tomli/chardet unchanged. Run for all five.
- Compiler commit `69e2dcd0` matches the `obs5` worktree HEAD. Requirements are pinned; no library source is vendored.
- Tests: `test_ail_wedge3`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 0 failed; `update_manifest.py --check` passes.
- Probes: `/tmp/rprobes/r_wedge3_mix.py`, `/tmp/rprobes/r_wedge3_plain.py` and the worker's three `/tmp/probes/wedge3_*` match CPython on g/d builds.

**False claims**
1. `DEVLOG.md:12` says “PyPy ran the pure libraries at 1.0-2.6x the hybrid's time.” Probe `/tmp/rprobes/ratios.py` shows PyPy/hybrid = 0.385..1.005; the 0.995..2.595 range is h/P (hybrid/PyPy), the reciprocal.
2. `RESULTS.md` headline’s “(0.33x-7.9x per pair)” and DEVLOG’s “7.9x/3.5x/3.4x/2.7x” are h/R values, not rewrite/CPython. Probe `ratios.py`: R/C range is 0.132..3.277 (jsonschema-rs 7.58x, rtoml 3.26x, rapidfuzz 3.16x, rustworkx 2.78x, chardet 3.28x slower). The 2.31x geomean is correct.

**Unverified**
- The “7-rep networkx re-run” and “medians of 5” cannot be checked from `results.json`, which stores only final medians.

**Pre-existing**
- None observed.

**Scope note**
- The task said “Commit only lab/wedge3/**”, but `AIL_CURRENT/test_ail_wedge3.py`, `tests.d`, `manifest.d` and `DEVLOG.md` are also committed. They are test/record files; no compiler behaviour changed.

VERDICT: FIX
1. Fix `RESULTS.md` headline and `DEVLOG.md` per-pair factors: use rewrite/CPython (`0.132..3.277`, i.e. 7.58x faster to 3.28x slower) or label the numbers as h/R.
2. Fix `DEVLOG.md:12`: state PyPy/hybrid `0.39..1.0x` (or hybrid is 1.0-2.6x PyPy’s time), not “PyPy … at 1.0-2.6x the hybrid’s time.”
[cost $0.0000, opencode tokens {"total": 1599738, "input": 42194, "output": 7123, "reasoning": 40533, "cache.write": 0, "cache.read": 1509888}]
    tool time: bash 7.9 min, write 0.0 min
        245s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_fil
        129s bash   cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_wedge3 test_ail_safetynet 2>&1 | ta
         47s bash   cd /home/runner/work/ail-ci/ail-ci && WEDGE_CPY=/tmp/wedge3venv/bin/python WEDGE_PYPY=/tmp/wedge3pypy/bin/pyth
         12s bash   cd /home/runner/work/ail-ci/ail-ci/lab/wedge3/workloads && PY=/tmp/wedge3venv/bin/python && for w in networkx 
         10s bash   cd /home/runner/work/ail-ci/ail-ci/lab/wedge3/workloads && PY=/tmp/wedge3pypy/bin/python && for w in networkx 
          9s bash   mkdir -p /tmp/revobs && cd /home/runner/work/ail-ci/ail-ci/lab/wedge3/workloads && PY=/tmp/wedge3venv/bin/pyth
          8s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/wedge3_int.py /tmp/probes/wedge3_list.py /tmp/probe
          7s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/r_wedge3_mix.py /tmp/rprobes/r_wedge3_plain.py; do

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review findings and committed as `093cf62f`.

- `lab/wedge3/RESULTS.md` headline: replaced `0.33x-7.9x` (h/R) with rewrite/CPython `0.132x-3.277x` (7.58x faster to 3.28x slower).
- `DEVLOG.md`: per-pair factors now labeled rewrite/CPython (7.58x/3.26x/3.15x/2.78x faster; charset-normalizer 3.28x slower) and PyPy/hybrid corrected to `0.39-1.0x` (hybrid 1.0-2.6x PyPy's time).

Verification on final commit:
- Probes `/tmp/probes/wedge3_{int,list,str}.py` and `/tmp/rprobes/r_wedge3_{plain,mix}.py`: CPython exit 0, g/d both same stdout.
- Required tests `test_ail_wedge3`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed.
- `python3 tools/update_manifest.py --check`: clean.
[cost $0.0000, opencode tokens {"total": 286119, "input": 44541, "output": 2577, "reasoning": 2713, "cache.write": 0, "cache.read": 236288}]
    tool time: bash 4.4 min, edit 0.0 min
        248s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_wed
         14s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/wedge3_int.py /tmp/probes/wedge3_list.py /tmp/probe
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -5
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add DEVLOG.md lab/wedge3/RESULTS.md && git commit -m "job wedge3: co
          0s edit   /home/runner/work/ail-ci/ail-ci/DEVLOG.md
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git diff --stat && sed -n '1,20p' /tmp/rprobes/r_wedge3_plain.py && echo
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -c " import json,math d=json.load(open('lab/wedge3/results.json'

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: job wedge3 (`work..HEAD`, 3 commits)

**What the change really does.** Adds a measurement-only artifact: `lab/wedge3/` (`measure.py`, five self-written workloads, pinned `requirements.txt`, `results.json`, `RESULTS.md`), a DEVLOG entry, and `test_ail_wedge3.py` + `tests.d`/`manifest.d` registration pinning the artifact. No compiler/runtime file is touched. Matches the report; no mismatch.

**Verified against the committed data**
- Ratios: recomputed from `results.json`: h/C geomean 1.045 (0.967–1.075), h/P 1.551, h/R 2.415; rewrite/CPython 0.132–3.277 → geomean 2.31x faster. HEAD fixes the labels correctly (DEVLOG 7.58x/3.26x/3.15x/2.78x and charset 3.28x slower; PyPy/hybrid 0.39–1.0x are right).
- Compiler provenance: `69e2dcd0…` is the tip of `origin/job-obs5-op1109`; `results.json` records `../obs5/AIL_CURRENT`. Refusal table sums reproduce exactly (4.082 / 3.511 / 1.888 / 0.084 / 0.009 / 0.001, base 9.575≈9.58 s).
- Re-ran `measure.py --only tomli,chardet --reps 1`: 0 native both configs, hybrid stdouts byte-identical to CPython, times within noise of the committed values. Reproducible.
- `test_ail_wedge3` + `test_ail_safetynet`: 2/2 pass; `update_manifest.py --check` clean; all five `/tmp/probes` and `/tmp/rprobes` programs pass `cmp.sh` (g/d same stdout). Installed venv versions match the pins.
- No DIFERENCES-worthy compiler output change: no compiler file changed, so C output is unchanged by construction.

**Minor / unverified (not blocking)**
- Per-category "functions" counts and example-function timings in §4 are not stored in `results.json` (profiles are deleted), so I could not re-derive them.
- §4 "outside … 2.14 s" is 2.153 s when summed from `results.json` (rounding-level).
- I did not independently re-verify the annotate-source changes for networkx/jsonschema/difflib, nor re-run `test_ail_files`/`test_ail_corpus_findings3` (review scope: changed module + safetynet only).
- "Commit only lab/wedge3/**" vs the mandated test-registration/DEVLOG/manifest updates is a scope tension, but the general rules require those records.

**Pre-existing differences:** none observed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 497251, "input": 54029, "output": 3427, "reasoning": 13939, "cache.write": 0, "cache.read": 425856}]
    tool time: bash 2.9 min
        130s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_wedg
         31s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 lab/wedge3/measure.py --only tomli,chardet --reps 1
         14s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/wedge3_int.py /tmp/probes/wedge3_list.py /tmp/probe
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rn "build.json\|accelerated" docs/design/OBSERVED_TYPES.md AIL_CUR
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "EXIT $?";
          0s bash   cd /home/runner/work/ail-ci/obs5 && sed -n '40,75p' AIL_CURRENT/DEVLOG.md && echo "=== build subcommand help =
          0s bash   cd /home/runner/work/ail-ci/ail-ci && sed -n '1,160p' AIL_CURRENT/ailc.py && echo "=== grep ext ===" && grep -
          0s bash   date && pwd && git status && git log --oneline work..HEAD && echo "---DIFF STAT---" && git diff --stat work..H

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-09T05:35:18Z
