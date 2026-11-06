# job job-fbpmap1-11061042  started 2026-11-06T01:42:45Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `213eebe` on `job-fbpmap1-11061042`; not pushed (runner says commit only, do not push).

- Added `lab/race/pmap/{par_collatz,uniform,ramp,heavy,tiny}.py`, `run.py`, `PMAP.md`, `PMAP.json`.
- Idle tail at 4 threads: heavy **80.3%**, ramp **15.8%**, par_collatz **2.2%**, uniform **0.7%**, tiny **0.7%** → **guided chunks: go**.
- Probe prefix: **0.06–0.10 ms** when wide; blocks: **1 / 17 / 33** at 1 / 2 / 4 threads (prefix leftover makes 17/33).
- Result-list time: par_collatz **6.9 ms**, uniform **4.1 ms**, heavy **1.6 ms**, ramp **0.07 ms**, tiny **9.1 ms** (tiny's list init dominates its 5 ms region).
- par_collatz wall at 1/2/4: **1363 / 716 / 542 ms**; races3 AIL 1271/886/603 ms. Local compare-lab at 4 threads: AIL **475 ms**, C **381 ms**, Rust **311 ms**.
- Nesting scan over 2,592 `lab/**/*.py` and test modules found **1** nested-region program (`lab/race/racy/nested_writes_outer.py`); rule needs 3 → **work stealing: no-go: no nesting**.
- Instruction counts unavailable: `perf_event_open` denied, `valgrind` absent.
- Tests: race probes **31 OK** (1 expected failure); files + corpus findings3 **20 OK** (1 skip); safetynet **5 OK** without the 1.5 GB cap (under the cap `S4_generators_gc` exceeds it). `update_manifest.py --check` clean.
[cost $0.0000, opencode tokens {"total": 6139796, "input": 162534, "output": 21956, "reasoning": 36458, "cache.write": 0, "cache.read": 5918848}]
    tool time: bash 14.8 min, write 0.0 min, edit 0.0 min
        260s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -m unittest AIL_CURRENT.test_ail_files AIL_CURRENT.test_ail_corp
        146s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -m unittest AIL_CURRENT.test_ail_safetynet.GeneralPathSafetyNet.
        110s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 lab/race/pmap/run.py --runs 5 2>&1 | tail -60
         99s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 -m unittest AIL_CURRENT.test_ail_safetynet 2>
         88s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 lab/race/pmap/run.py --loads ramp,heavy,tiny,par_collatz --
         77s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 -m unittest AIL_CURRENT.test_ail_race_probes 
         71s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; time python3 lab/compare/run_task.py --task par_colla
          6s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('lab/race/pmap/run.py')

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of fbpmap1 (`work..HEAD`, commit `213eebe`)**

**What the diff really does:** adds only `lab/race/pmap/{run.py,par_collatz.py,uniform.py,ramp.py,heavy.py,tiny.py}` plus `lab/race/PMAP.{md,json}`. No compiler/runtime/test/benchmark change. `run.py` instruments a scratch copy of the generated `program.c` in `/tmp` (block timestamps, probe-prefix stamp, result-list init stamp), measures at `AIL_THREADS` 1/2/4, and writes the report. This matches the report.

**Probes / checks run**
- Re-ran the five loads in a `/tmp` mirror of `run.py` (`--runs 2`); region/tail/prefix/block numbers reproduce the committed ones. Tail shares at 4 threads: heavy 80.3%, ramp 15.7%, par_collatz 1.4%, uniform 0.3%, tiny 0.9% → guided **go** is correct.
- `cmp.sh` on `uniform`, `ramp`, `heavy`, `tiny`: CPython, general path (`AIL_UNIFIED_FORCE=1`) and default all identical.
- Compiled a non-parallel and a typed-parallel probe on HEAD and `/tmp/base` (`work`): `program.c` byte-identical → no compiler drift.
- Independent nesting scan (own AST walker over `lab/**/*.py` and embedded AIL strings in `AIL_CURRENT/test_*.py`): 1 program, `lab/race/racy/nested_writes_outer.py`; none hidden in test source strings → **no-go: no nesting** is correct.
- `perf_event_paranoid=4`, `perf_event_open` denied, `valgrind` absent → instruction counts genuinely unavailable.
- `test_ail_safetynet` via `par_check.py -j 2`: **ok, 0 failed**. `update_manifest.py --check`: clean. `git diff work..HEAD` touches only `lab/race/`.

**Claim audit**
- Files, idle tails, prefix `0.057–0.103 ms`, blocks `1/17/33`, list times, par_collatz walls: **verified**.
- Nesting count 1 and both go/no-go lines: **verified**.
- Instruction-count unavailability: **verified**.
- `list_ms` is the serial `[0]*n` init before the region, not the in-region result writes; the report says so explicitly, so not a false claim, but it is narrower than "time to write the results list".
- Local compare-lab 4-thread numbers: **unverified** (hardcoded in `run.py`, not re-run).

**Pre-existing:** none found.

**Unverified / gaps:** compare-lab at 1 and 2 threads was not run (sub-step 2 asks for 1/2/4); only the 4-thread local run is recorded. This does not affect the decision numbers. Race/file/corpus tests and the 20 shards were not re-run per reviewer scope / not pushed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1715795, "input": 77125, "output": 8893, "reasoning": 24657, "cache.write": 0, "cache.read": 1605120}]
    tool time: bash 4.8 min
        155s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 600 python3 ../tools/par_check.py -j 2 test_
         96s bash   cd /tmp/rprobes/mirror && date && timeout 900 python3 lab/race/pmap/run.py --runs 2 --skip-nesting 2>&1 | tail
         26s bash   cd /tmp && for f in uniform ramp heavy tiny; do echo "######## $f"; bash ~/tools/cmp.sh /home/runner/work/ail-
          3s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import importlib.util,json spec=importlib.util.spec_fro
          3s bash   mkdir -p /tmp/rprobes/cmp && cat > /tmp/rprobes/cmp/simple.py <<'PY' def main():     print(1 + 2) main() PY ca
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import ast,importlib.util,pathlib spec=importlib.util.s
          1s bash   cat > /tmp/nestscan.py <<'PY' import ast, pathlib, sys ROOT=pathlib.Path('/home/runner/work/ail-ci/ail-ci')  d
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add -f /tmp/base work >/dev/null 2>&1 && echo added; ls /tm

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T03:58:46Z
